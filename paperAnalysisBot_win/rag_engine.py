# rag_engine.py
import os
from pathlib import Path
from typing import Optional
import concurrent.futures
import shutil
import torch
import faiss

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings
from llama_index.vector_stores.faiss import FaissVectorStore  # FAISS 사용
from config import Config
from pymupdf4llm import to_markdown
import pymupdf  # fallback용 미리 import


class RAGEngine:
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self.paper_dir = Config.PAPER_DIR
        self.index = None
        self.query_engine = None

        # LLM 및 임베딩 설정
        current_config = Config.get_current_llm_config()
        Settings.llm = Ollama(
            model=current_config["model"],
            base_url=current_config["api_base"],
            request_timeout=current_config.get("timeout", 1200.0),
            temperature=current_config["temperature"]
        )
        Settings.embed_model = HuggingFaceEmbedding(model_name=Config.EMBEDDING_MODEL)
        Settings.chunk_size = Config.CHUNK_SIZE
        Settings.chunk_overlap = Config.CHUNK_OVERLAP

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
                doc = pymupdf.open(str(pdf_path))
                text_pages = [page.get_text("text") for page in doc]
                md_text = "\n\n".join(text_pages)
                doc.close()
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

    def build_or_load_index(self, clean: bool = False):
        """인덱스 생성 또는 로드 (FAISS 사용)"""
        faiss_index_path = self.data_dir / "faiss_index"
        faiss_index_file = faiss_index_path / "index.faiss"

        # clean=True면 기존 인덱스 삭제
        if clean and faiss_index_path.exists():
            print("clean=True: 기존 FAISS 인덱스 삭제 후 재생성")
            shutil.rmtree(faiss_index_path)

        # 기존 인덱스 로드 시도
        if faiss_index_file.exists():
            try:
                print("기존 FAISS 인덱스 로드 중...")
                faiss_index = faiss.read_index(str(faiss_index_file))
                vector_store = FaissVectorStore(faiss_index=faiss_index)
                storage_context = StorageContext.from_defaults(
                    vector_store=vector_store,
                    persist_dir=str(faiss_index_path)
                )
                self.index = load_index_from_storage(storage_context)
                self.query_engine = self.index.as_query_engine(similarity_top_k=5)
                print("기존 인덱스 로드 완료! 이제 쿼리 가능")
                return self.query_engine
            except Exception as e:
                print(f"인덱스 로드 실패 → 새로 생성 ({e})")

        # 새 인덱스 생성
        print("새 FAISS 인덱스 생성 시작...")
        converted = self.convert_pdf_to_md(force_reconvert=clean)

        md_files = list(self.data_dir.glob("*.md"))
        if not md_files:
            print("data 폴더에 MD 파일이 없어요.")
            return None

        print(f"{len(md_files)}개 Markdown 파일 로드 중...")
        documents = SimpleDirectoryReader(
            input_files=md_files,
            filename_as_id=True
        ).load_data()

        if not documents:
            print("문서 로드 실패")
            return None

        print("임베딩 생성 및 FAISS 인덱스 빌드 시작...")
        if torch.cuda.is_available():
            print(f"GPU 가속 사용 중: {torch.cuda.get_device_name(0)}")
        else:
            print("GPU 사용 불가 - CPU 모드로 임베딩 생성")

        test_text = "dimension test"
        test_embedding = Settings.embed_model.get_text_embedding(test_text)
        embed_dim = len(test_embedding)
        print(f"임베딩 차원: {embed_dim}")

        faiss_index = faiss.IndexFlatL2(embed_dim)
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        splitter = SentenceSplitter(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
        self.index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            node_parser=splitter
        )

        # 저장
        faiss_index_path.mkdir(parents=True, exist_ok=True)
        self.index.storage_context.persist(persist_dir=str(faiss_index_path))

        self.query_engine = self.index.as_query_engine(similarity_top_k=5)
        print("FAISS 인덱스 생성 및 저장 완료! 이제 쿼리 가능")
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