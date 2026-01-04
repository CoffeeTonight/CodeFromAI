# rag_engine.py
import os
from pathlib import Path
from typing import Optional
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings
import chromadb
import torch
from config import Config
from pymupdf4llm import to_markdown
import concurrent.futures

class RAGEngine:
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self.paper_dir = Config.PAPER_DIR
        self.chroma_db_path = self.data_dir / "chroma_db"
        self.index = None
        self.query_engine = None

        # LLM 및 임베딩 설정 (config에서 가져옴)
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

        existing_md = {f.stem for f in self.data_dir.iterdir() if f.suffix.lower() == ".md"}
        pdfs_to_convert = [
            p for p in self.paper_dir.iterdir()
            if p.suffix.lower() == ".pdf" and p.stem not in existing_md
        ]

        skip_count = total_pdfs - len(pdfs_to_convert)

        print(f"총 PDF 파일: {total_pdfs}개")
        print(f"이미 변환된 MD 파일: {skip_count}개 → 스킵")
        print(f"이번에 변환할 파일: {len(pdfs_to_convert)}개")

        if not pdfs_to_convert:
            print("변환할 새로운 PDF가 없습니다.")
            return 0

        print(f"\n{len(pdfs_to_convert)}개 PDF 변환 시작...\n")

        def convert_single(pdf_path: Path) -> int:
            md_path = self.data_dir / (pdf_path.stem + ".md")
            print(f"변환 중: {pdf_path.name}")
            try:
                md_text = to_markdown(str(pdf_path))
            except Exception as e:
                print(f"경고: {pdf_path.name} 변환 실패 → 기본 텍스트 추출 ({e})")
                import pymupdf  # fallback용
                doc = pymupdf.open(str(pdf_path))
                text_pages = [page.get_text("text") for page in doc]
                md_text = "\n\n".join(text_pages)
                doc.close()
            md_path.write_text(md_text, encoding="utf-8")
            return 1

        # 멀티스레드 변환
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
    
    def build_or_load_index(self):
        """인덱스 생성 또는 로드"""
        chroma_client = chromadb.PersistentClient(path=str(self.chroma_db_path))
        chroma_collection = chroma_client.get_or_create_collection("rag_collection")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        try:
            count = chroma_collection.count()
            if count > 0:
                print("기존 인덱스 로드 중...")
                self.index = load_index_from_storage(storage_context)
            else:
                raise ValueError("Empty collection")
        except Exception as e:
            print(f"새 인덱스 생성 중... (이유: {e})")

            converted = self.convert_pdf_to_md()
            if converted == 0:
                print("새로운 PDF가 없어요. 기존 MD 파일 사용.")

            md_files = list(self.data_dir.glob("*.md"))
            if not md_files:
                print("data 폴더에 MD 파일이 없어요.")
                return None

            print(f"{len(md_files)}개 Markdown 파일 강제 로드 중...")
            documents = SimpleDirectoryReader(
                input_files=md_files,
                filename_as_id=True
            ).load_data()

            if not documents:
                print("문서 로드 실패")
                return None

            print("임베딩 생성 및 인덱스 빌드 시작...")
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                print(f"GPU 가속 사용 중: {gpu_name}")
            else:
                print("GPU 사용 불가 - CPU 모드로 임베딩 생성")

            splitter = SentenceSplitter(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                node_parser=splitter
            )

        self.query_engine = self.index.as_query_engine(similarity_top_k=5)
        print("인덱스 생성 완료! 이제 쿼리 가능")
        return self.query_engine

    def query(self, question: str) -> str:
        """RAG 쿼리 실행"""
        if self.query_engine is None:
            self.build_or_load_index()
        response = self.query_engine.query(question)
        return str(response)


# __main__ 테스트
if __name__ == "__main__":
    print("=== RAG Engine 테스트 시작 ===")
    engine = RAGEngine()

    print("인덱스 빌드 시작...")
    query_engine = engine.build_or_load_index()
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