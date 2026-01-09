# core/rag_engine.py
import os
import shutil
from pathlib import Path
from typing import Optional
import concurrent.futures
import torch

from llama_index.core import VectorStoreIndex, StorageContext, Document, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI  # 회사 LLM용
from llama_index.llms.ollama import Ollama  # Ollama용
from llama_index.core import Settings

from core.config import Config
from core.utils import get_logger  # 중앙 로거 사용
from pymupdf4llm import to_markdown
import pymupdf

# 전역 싱글톤
_engine_instance = None

logger = get_logger("RAGEngine")

def get_rag_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RAGEngine()
        _engine_instance.build_or_load_index()  # 최초 1회만
    return _engine_instance

class RAGEngine:
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self.paper_dir = Config.PAPER_DIR
        self.index = None
        self.query_engine = None  # 기존 query_engine 대신 수동 RAG 사용

        # LLM 설정 (config에서 type에 따라 자동 분기)
        current_config = Config.get_current_llm_config()
        llm_type = current_config.get("type", "ollama")

        if llm_type == "ollama":
            self.llm = Ollama(
                model=current_config["model"],
                base_url=current_config["api_base"],
                request_timeout=current_config.get("timeout", 1200.0),
                temperature=current_config.get("temperature", 0.3)
            )
            logger.info(f"[LLM] Ollama 사용: {current_config['model']}")
        elif llm_type == "openai_compatible":
            self.llm = OpenAI(
                model=current_config["model"],
                api_base=current_config["api_url"],
                api_key=current_config["api_key"],
                max_tokens=current_config.get("max_tokens", 8192),
                temperature=current_config.get("temperature", 0.3),
                request_timeout=current_config.get("timeout", 180)
            )
            logger.info(f"[LLM] 회사 LLM 사용: {current_config['model']} ({current_config['api_url']})")
        else:
            raise ValueError(f"지원하지 않는 LLM 타입: {llm_type}")

        # 글로벌 Settings 적용
        Settings.llm = self.llm
        Settings.embed_model = HuggingFaceEmbedding(model_name=Config.EMBEDDING_MODEL)
        Settings.chunk_size = Config.CHUNK_SIZE
        Settings.chunk_overlap = Config.CHUNK_OVERLAP

    def _cleanup_orphan_md(self):
        """PDF 없는 MD 파일 자동 삭제 (모든 서브폴더)"""
        all_paper_dirs = [
            Config.ARXIV_PAPER_DIR,
            Config.SEMANTIC_PAPER_DIR,
            Config.CONFERENCE_PAPER_DIR,
            Config.USER_PAPER_DIR
        ]

        deleted = 0
        for paper_subdir in all_paper_dirs:
            if not paper_subdir.exists():
                continue
            data_subdir = Config.DATA_DIR / paper_subdir.name
            if not data_subdir.exists():
                continue

            existing_pdfs = {p.stem for p in paper_subdir.glob("*.pdf")}
            for md_file in data_subdir.glob("*.md"):
                if md_file.stem not in existing_pdfs:
                    logger.info(f"[정리] PDF 없음 → MD 삭제: {md_file}")
                    md_file.unlink(missing_ok=True)
                    deleted += 1
        if deleted:
            logger.info(f"[정리 완료] {deleted}개 고아 MD 파일 삭제")

    def convert_pdf_to_md(self, force_reconvert: bool = False):
        logger.info("PDF → MD 변환 시작")

        # 고아 MD 정리
        self._cleanup_orphan_md()

        total_converted = 0

        for paper_subdir in [Config.ARXIV_PAPER_DIR, Config.SEMANTIC_PAPER_DIR, Config.CONFERENCE_PAPER_DIR, Config.USER_PAPER_DIR]:
            if not paper_subdir.exists():
                continue

            data_subdir = Config.DATA_DIR / paper_subdir.name
            data_subdir.mkdir(parents=True, exist_ok=True)

            existing_md = {f.stem for f in data_subdir.glob("*.md")} if data_subdir.exists() else set()

            pdfs_to_convert = [
                p for p in paper_subdir.glob("*.pdf")
                if force_reconvert or p.stem not in existing_md
            ]

            logger.info(f"{paper_subdir.name} 폴더: {len(pdfs_to_convert)}개 변환 대상")

            for pdf_path in pdfs_to_convert:
                md_path = data_subdir / (pdf_path.stem + ".md")
                logger.info(f"변환 중: {pdf_path.name}")
                try:
                    md_text = to_markdown(str(pdf_path))
                except Exception as e:
                    logger.warning(f"{pdf_path.name} 변환 실패 → fallback 사용 ({e})")
                    try:
                        doc = pymupdf.open(str(pdf_path))
                        md_text = "\n\n".join(page.get_text("text") for page in doc)
                        doc.close()
                    except Exception as fe:
                        logger.error(f"fallback 실패: {fe}")
                        md_text = f"[PDF 변환 실패: {pdf_path.name}]"
                md_path.write_text(md_text, encoding="utf-8")
                total_converted += 1

        logger.info(f"총 {total_converted}개 PDF 변환 완료")
        return total_converted

    def build_or_load_index(self, clean: bool = False):
        persist_dir = str(self.data_dir / "faiss_index")

        if clean and os.path.exists(persist_dir):
            logger.info("clean=True: 기존 인덱스 삭제")
            shutil.rmtree(persist_dir)

        # 고아 정리 + 변환
        self._cleanup_orphan_md()
        self.convert_pdf_to_md()

        md_files = list(self.data_dir.rglob("*.md"))
        if not md_files:
            logger.error("MD 파일 없음 → 인덱스 생성 불가")
            return None

        logger.info(f"총 {len(md_files)}개 MD 파일 (모든 출처) 로드")

        documents = []
        for md_path in md_files:
            try:
                text = md_path.read_text(encoding="utf-8", errors="replace")
                source_type = md_path.parent.name
                documents.append(Document(
                    text=text,
                    metadata={
                        "source": md_path.stem,
                        "source_type": source_type,
                        "file_path": str(md_path)
                    }
                ))
            except Exception as e:
                logger.error(f"MD 읽기 실패 {md_path}: {e}")

        if not documents:
            logger.error("문서 로드 실패")
            return None

        node_parser = SentenceSplitter(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
        nodes = node_parser.get_nodes_from_documents(documents)
        logger.info(f"{len(nodes)}개 노드 생성")

        try:
            if os.path.exists(persist_dir):
                logger.info("기존 인덱스 로드")
                storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
                self.index = load_index_from_storage(storage_context, embed_model=Settings.embed_model)
            else:
                logger.info("새 인덱스 생성 시작")
                self.index = VectorStoreIndex(
                    nodes=nodes,
                    embed_model=Settings.embed_model,
                    show_progress=True
                )
                self.index.storage_context.persist(persist_dir=persist_dir)
                logger.info("새 인덱스 생성 및 저장 완료")

            logger.info("통합 RAG 인덱스 준비 완료! (수동 RAG 모드)")
            return self.index  # query_engine 대신 index 반환 (수동 사용)

        except Exception as e:
            logger.error(f"인덱스 처리 실패: {e}")
            return None

    def manual_rag_query(self, question: str, top_k: int = 15) -> str:
        """
        회사 LLM에서 top_k 지원 안 할 때 수동으로 RAG 수행
        top_k: 검색할 관련 청크 수 (회사 LLM은 15~25 추천)
        """
        if self.index is None:
            logger.warning("인덱스 없음 → 빌드 시도")
            self.build_or_load_index()
        if self.index is None:
            return "RAG 인덱스 준비 실패"

        logger.info(f"수동 RAG 쿼리 시작 (top_k={top_k}): {question}")

        # Retriever로 top_k개 청크 검색
        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(question)

        if not nodes:
            logger.info("관련 문서 없음")
            return "관련 문서를 찾을 수 없습니다."

        # 컨텍스트 구성
        context_parts = []
        for i, node in enumerate(nodes, 1):
            source_type = node.metadata.get("source_type", "unknown")
            source = node.metadata.get("source", "제목 없음")
            context_parts.append(f"[문서 {i} | 출처: {source_type} | 파일: {source}]\n{node.text}\n")

        context = "\n".join(context_parts)

        # 프롬프트
        prompt = f"""
너는 반도체 SoC 설계 및 검증 분야의 전문가다.
아래 제공된 문서들을 바탕으로 질문에 정확하고 전문적으로 답변해 주세요.
답변은 한국어로 해주세요.

질문: {question}

참고 문서들:
{context}

답변:
"""

        try:
            response = Settings.llm.complete(prompt)
            answer = str(response.text)
            logger.info("수동 RAG 쿼리 성공")
            return answer
        except Exception as e:
            logger.error(f"회사 LLM 호출 실패: {e}")
            return f"답변 생성 실패: {str(e)}"

    def query(self, question: str) -> str:
        """
        외부에서 호출하는 공용 쿼리 함수
        회사 LLM 호환을 위해 manual_rag_query 사용
        """
        return self.manual_rag_query(question, top_k=15)  # 회사 LLM용 추천값

if __name__ == "__main__":
    logger.info("=== RAG Engine 테스트 시작 ===")
    engine = RAGEngine()
    engine.build_or_load_index(clean=False)

    test_questions = [
        "반도체 설계에서 LLM이 어떻게 사용되고 있나요?",
        "최근 UVM 관련 논문 요약해줘",
        "오픈소스 프로젝트가 있는 논문은?"
    ]

    for q in test_questions:
        logger.info(f"\nQ: {q}")
        answer = engine.query(q)
        logger.info(f"A: {answer[:500]}...")
