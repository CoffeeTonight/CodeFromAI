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
from pymupdf4llm import to_markdown
import pymupdf

class RAGEngine:
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self.paper_dir = Config.PAPER_DIR
        self.index = None
        self.query_engine = None

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
            print(f"[LLM] Ollama 사용: {current_config['model']}")
        elif llm_type == "openai_compatible":
            self.llm = OpenAI(
                model=current_config["model"],
                api_base=current_config["api_url"],
                api_key=current_config["api_key"],
                max_tokens=current_config.get("max_tokens", 8192),
                temperature=current_config.get("temperature", 0.3),
                request_timeout=current_config.get("timeout", 180),
                # 인증서 필요 시
                # http_client=your_custom_session
            )
            print(f"[LLM] 회사 LLM 사용: {current_config['model']} ({current_config['api_url']})")
        else:
            raise ValueError(f"지원하지 않는 LLM 타입: {llm_type}")

        # 글로벌 Settings 적용
        Settings.llm = self.llm
        Settings.embed_model = HuggingFaceEmbedding(model_name=Config.EMBEDDING_MODEL)
        Settings.chunk_size = Config.CHUNK_SIZE
        Settings.chunk_overlap = Config.CHUNK_OVERLAP

    def _cleanup_orphan_md(self):
        """PDF 없는 MD 파일 자동 삭제 (RAG 정합성 유지)"""
        existing_pdfs = {p.stem for p in self.paper_dir.glob("*.pdf")}
        deleted = 0
        for md_file in self.data_dir.glob("*.md"):
            if md_file.stem not in existing_pdfs:
                print(f"[정리] PDF 삭제됨 → MD 자동 삭제: {md_file.name}")
                md_file.unlink(missing_ok=True)
                deleted += 1
        if deleted:
            print(f"[정리 완료] {deleted}개 고아 MD 파일 삭제")

    def convert_pdf_to_md(self, force_reconvert: bool = False):
        """PDF → MD 변환 + 고아 MD 정리"""
        print("PDF → MD 변환 시작")

        # 고아 MD 정리
        self._cleanup_orphan_md()

        total_pdfs = len(list(self.paper_dir.glob("*.pdf")))
        print(f"총 PDF 파일: {total_pdfs}개")

        if force_reconvert:
            print("강제 재변환: 기존 MD 모두 삭제")
            for md_file in self.data_dir.glob("*.md"):
                md_file.unlink(missing_ok=True)

        existing_md = {f.stem for f in self.data_dir.glob("*.md")}
        pdfs_to_convert = [
            p for p in self.paper_dir.glob("*.pdf")
            if force_reconvert or p.stem not in existing_md
        ]

        print(f"이번에 변환할 파일: {len(pdfs_to_convert)}개")

        if not pdfs_to_convert:
            print("새로운 변환 대상 없음")
            return 0

        def convert_single(pdf_path: Path):
            md_path = self.data_dir / (pdf_path.stem + ".md")
            print(f"변환 중: {pdf_path.name}")
            try:
                md_text = to_markdown(str(pdf_path))
            except Exception as e:
                print(f"경고: {pdf_path.name} 변환 실패 → fallback ({e})")
                try:
                    doc = pymupdf.open(str(pdf_path))
                    md_text = "\n\n".join(page.get_text("text") for page in doc)
                    doc.close()
                except Exception as fe:
                    print(f"fallback 실패: {fe}")
                    md_text = f"[PDF 변환 실패: {pdf_path.name}]"
            md_path.write_text(md_text, encoding="utf-8")
            return 1

        converted = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(convert_single, p) for p in pdfs_to_convert]
            for future in concurrent.futures.as_completed(futures):
                converted += future.result()

        print(f"변환 완료: {converted}개")
        return converted

    def build_or_load_index(self, clean: bool = False):
        persist_dir = str(self.data_dir / "faiss_index")

        if clean and os.path.exists(persist_dir):
            print("clean=True: 기존 인덱스 삭제")
            shutil.rmtree(persist_dir)

        # 고아 정리 + 변환
        self._cleanup_orphan_md()
        self.convert_pdf_to_md()

        md_files = list(self.data_dir.glob("*.md"))
        if not md_files:
            print("MD 파일 없음 → 인덱스 생성 불가")
            return None

        print(f"{len(md_files)}개 MD 파일로 인덱스 처리")

        # 문서 로드 (인코딩 안전)
        documents = []
        for md_path in md_files:
            try:
                text = md_path.read_text(encoding="utf-8", errors="replace")
                documents.append(Document(text=text, metadata={"source": md_path.stem}))
            except Exception as e:
                print(f"MD 읽기 실패 {md_path.name}: {e}")
                continue

        if not documents:
            print("문서 로드 실패")
            return None

        # 노드 분할
        node_parser = SentenceSplitter(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
        nodes = node_parser.get_nodes_from_documents(documents)
        print(f"{len(nodes)}개 노드 생성")

        # 인덱스 로드/생성 (LlamaIndex 공식 방식)
        try:
            if os.path.exists(persist_dir):
                print("기존 인덱스 로드 시도")
                storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
                self.index = load_index_from_storage(
                    storage_context=storage_context,
                    embed_model=Settings.embed_model
                )
                print("기존 인덱스 로드 성공")
            else:
                print("새 인덱스 생성 시작")
                self.index = VectorStoreIndex(
                    nodes=nodes,
                    embed_model=Settings.embed_model,
                    show_progress=True
                )
                self.index.storage_context.persist(persist_dir=persist_dir)
                print("새 인덱스 생성 및 저장 완료")

            self.query_engine = self.index.as_query_engine(similarity_top_k=5)
            print("RAG 엔진 준비 완료!")
            return self.query_engine

        except Exception as e:
            print(f"인덱스 처리 실패: {e}")
            return None

    def query(self, question: str) -> str:
        if self.query_engine is None:
            print("query_engine 없음 → 재시도")
            self.build_or_load_index()
        if self.query_engine is None:
            return "RAG 엔진이 준비되지 않았습니다."
        try:
            response = self.query_engine.query(question)
            return str(response)
        except Exception as e:
            return f"쿼리 실패: {str(e)}"


if __name__ == "__main__":
    print("=== RAG Engine 테스트 시작 ===")
    engine = RAGEngine()
    engine.build_or_load_index(clean=False)

    test_questions = [
        "반도체 설계에서 LLM이 어떻게 사용되고 있나요?",
        "최근 UVM 관련 논문 요약해줘",
        "오픈소스 프로젝트가 있는 논문은?"
    ]

    for q in test_questions:
        print(f"\nQ: {q}")
        answer = engine.query(q)
        print(f"A: {answer[:500]}...")