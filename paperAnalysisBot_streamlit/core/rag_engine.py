# rag_engine.py
import os
from typing import Optional
import concurrent.futures
import shutil
import torch
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings, Document
from llama_index.vector_stores.faiss import FaissVectorStore  # FAISS 사용
from config import Config
from pymupdf4llm import to_markdown
import pymupdf  # fallback용 미리 import
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from pathlib import Path
import faiss
import pickle
from functools import lru_cache

@lru_cache(maxsize=1)
def get_rag_engine():
    """RAGEngine 싱글톤 반환"""
    engine = RAGEngine()
    engine.build_or_load_index()  # 한 번만 실행
    return engine

class RAGEngine:
    def __init__(self):
        current_config = Config.get_current_llm_config()
        self.llm = Ollama(
            model=current_config["model"],
            base_url=current_config["api_base"],
            request_timeout=current_config.get("timeout", 3600.0),
            temperature=current_config["temperature"]
        )

        # 폴더 초기화
        self.paper_dir = Config.PAPER_DIR
        self.data_dir = Config.DATA_DIR
        self.paper_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # StorageContext 초기화 (IndexStorageContext 대신)
        self.storage_context = StorageContext.from_defaults()

        # Settings 설정
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=Config.EMBEDDING_MODEL,
            device="cpu"
        )
        Settings.chunk_size = Config.CHUNK_SIZE
        Settings.chunk_overlap = Config.CHUNK_OVERLAP
        Settings.llm = self.llm
        self.query_engine = None

    def convert_pdf_to_md(self, force_reconvert: bool = False):
        """paper 폴더의 모든 PDF를 Markdown으로 변환"""
        total_pdfs = len([p for p in self.paper_dir.iterdir() if p.suffix.lower() == ".pdf"])

        if force_reconvert:
            print("force_reconvert=True: 기존 MD 파일 모두 삭제 후 재생성")
            for md_file in self.data_dir.glob("*.md"):
                md_file.unlink(missing_ok=True)
            existing_md = set()
            skip_count = 0
        else:
            existing_md = {f.stem for f in self.data_dir.iterdir() if f.suffix.lower() == ".md"}
            skip_count = total_pdfs - len([p for p in self.paper_dir.iterdir()
                                           if p.suffix.lower() == ".pdf" and p.stem not in existing_md])

        print(f"총 PDF 파일: {total_pdfs}개")
        print(f"이미 변환된 MD 파일: {skip_count}개 → 스킵")
        print(f"이번에 변환할 파일: {total_pdfs - skip_count}개\n")

        pdfs_to_convert = [
            p for p in self.paper_dir.iterdir()
            if p.suffix.lower() == ".pdf" and (force_reconvert or p.stem not in existing_md)
        ]

        if not pdfs_to_convert:
            print("변환할 새로운 PDF가 없습니다.")
            return 0

        print(f"{len(pdfs_to_convert)}개 PDF 변환 시작...\n")

        def convert_single(pdf_path: Path) -> int:
            md_path = self.data_dir / (pdf_path.stem + ".md")
            print(f"변환 중: {pdf_path.name}")
            try:
                md_text = to_markdown(str(pdf_path))
            except Exception as e:
                print(f"경고: {pdf_path.name} 변환 실패 → 기본 텍스트 추출 ({e})")
                try:
                    doc = pymupdf.open(str(pdf_path))
                    text_pages = []
                    for page in doc:
                        try:
                            text_pages.append(page.get_text("text"))
                        except:
                            text_pages.append("")  # 페이지 오류 무시
                    md_text = "\n\n".join(text_pages)
                    doc.close()
                except Exception as fallback_e:
                    print(f"fallback도 실패: {fallback_e}")
                    md_text = f"[PDF 변환 완전 실패: {pdf_path.name}]"
            md_path.write_text(md_text, encoding="utf-8")
            return 1

        converted = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(convert_single, p) for p in pdfs_to_convert]
            for future in concurrent.futures.as_completed(futures):
                try:
                    converted += future.result()
                except Exception as e:
                    print(f"스레드 오류: {e}")

        print(f"\n{converted}개 PDF 변환 완료!")
        return converted

    # core/rag_engine.py 내 함수
    def build_or_load_index(self, clean: bool = False):
        """FAISS 인덱스 로드 또는 생성 (텍스트 저장 포함)"""
        faiss_index_path = self.data_dir / "faiss_index"
        faiss_index_file = faiss_index_path / "index.faiss"
        documents_file = faiss_index_path / "documents.pkl"

        # clean 모드면 기존 인덱스 삭제
        if clean:
            if faiss_index_path.exists():
                import shutil
                shutil.rmtree(faiss_index_path)
                print("기존 인덱스 삭제 - 강제 재생성")

        # 기존 인덱스 존재하면 로드
        if faiss_index_file.exists() and documents_file.exists():
            print("기존 FAISS 인덱스 로드")
            index = faiss.read_index(str(faiss_index_file))
            with open(documents_file, "rb") as f:
                documents = pickle.load(f)
            vector_store = FaissVectorStore(faiss_index=index)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            # 텍스트 저장된 documents 사용
            vector_index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=Settings.embed_model
            )
            self.query_engine = vector_index.as_query_engine(similarity_top_k=5)
            return self.query_engine

        # PDF 변환
        converted = self.convert_pdf_to_md()
        if converted == 0:
            print("새로운 PDF 없음 - 기존 인덱스 재로드 시도")
            if faiss_index_file.exists() and documents_file.exists():
                print("기존 인덱스 로드 성공")
                index = faiss.read_index(str(faiss_index_file))
                with open(documents_file, "rb") as f:
                    documents = pickle.load(f)
                vector_store = FaissVectorStore(faiss_index=index)
                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                vector_index = VectorStoreIndex.from_documents(
                    documents,
                    storage_context=storage_context,
                    embed_model=Settings.embed_model
                )
                self.query_engine = vector_index.as_query_engine(similarity_top_k=5)
                return self.query_engine

        # 새 인덱스 생성
        print("새 FAISS 인덱스 생성 시작...")
        md_files = list(self.data_dir.glob("*.md"))
        if not md_files:
            print("MD 파일 없음 - 변환 실패")
            return None

        print(f"{len(md_files)}개 Markdown 파일 로드 중...")
        documents = []
        for md_path in md_files:
            with open(md_path, "r", encoding="utf-8") as f:
                text = f.read()
            metadata = {"source": md_path.stem}
            documents.append(Document(text=text, metadata=metadata))

        print("임베딩 생성 및 FAISS 인덱스 빌드 시작...")
        dimension = len(Settings.embed_model.get_text_embedding("test"))
        faiss_index = faiss.IndexFlatL2(dimension)
        vector_store = FaissVectorStore(faiss_index=faiss_index)

        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        vector_index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=Settings.embed_model
        )

        # 저장 (텍스트 + 임베딩)
        faiss_index_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(faiss_index, str(faiss_index_file))
        with open(documents_file, "wb") as f:
            pickle.dump(documents, f)

        print("FAISS 인덱스 생성 및 저장 완료! 이제 쿼리 가능")

        self.query_engine = vector_index.as_query_engine(similarity_top_k=5)
        return self.query_engine

    def query(self, question: str) -> str:
        if self.query_engine is None:
            self.build_or_load_index()
        response = self.query_engine.query(question)
        return str(response)


if __name__ == "__main__":
    print("=== RAG Engine 테스트 시작 ===")
    engine = RAGEngine()

    print("인덱스 빌드 시작...")
    query_engine = engine.build_or_load_index(clean=False)  # 필요시 clean=True
    if query_engine is None:
        print("인덱스 생성 실패")
    else:
        print("인덱스 준비 완료!")

        test_questions = [
            "반도체 설계에서 LLM이 어떻게 사용되고 있나요?",
            "최근 UVM 관련 논문 요약해줘",
            "오픈소스 프로젝트가 있는 논문은?"
        ]

        print("\n테스트 쿼리 실행:")
        for q in test_questions:
            print(f"\nQ: {q}")
            answer = engine.query(q)
            print(f"A: {answer[:500]}...")

    print("\nRAG Engine 테스트 완료!")