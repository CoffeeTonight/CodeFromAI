# core/rag_engine.py
import os
import shutil
from pathlib import Path
from typing import Optional
import concurrent.futures
import torch
import httpx  # 회사 API 호출용

from llama_index.core import VectorStoreIndex, StorageContext, Document, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import CustomLLM, LLMMetadata
from llama_index.core.llms.llms import CompletionResponse
from llama_index.core import Settings

from core.config import Config
from core.utils import get_logger
from pymupdf4llm import to_markdown
import pymupdf

logger = get_logger("RAGEngine")

# 싱글톤
_engine_instance = None

def get_rag_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RAGEngine()
        _engine_instance.build_or_load_index()
    return _engine_instance

# 회사 LLM 전용 CustomLLM 구현
class CompanyLLM(CustomLLM):
    model_name: str = "company-llm"
    api_url: str = None
    api_key: str = None
    user_key: str = None
    cert_path: str = None
    timeout: int = 180

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        current_config = Config.get_current_llm_config()
        self.api_url = current_config["api_url"]
        self.api_key = current_config["api_key"]
        self.user_key = current_config.get("user_key")
        self.cert_path = current_config.get("cert_path")
        self.timeout = current_config.get("timeout", 180)
        self.model_name = current_config["model"]

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=32768,  # 회사 LLM 컨텍스트 길이
            num_output=8192
        )

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """회사 API의 send_query 인터페이스 사용"""
        try:
            # 회사 API 클래스 직접 호출 (가정: CompanyAPI 클래스 존재)
            # 만약 별도 모듈에 있다면 from company_api import CompanyAPI
            from company_api import CompanyAPI  # 회사에서 제공한 모듈 import

            api = CompanyAPI(
                api_url=self.api_url,
                api_key=self.api_key,
                user_key=self.user_key,
                cert_path=self.cert_path,
                model=self.model_name,
                timeout=self.timeout
            )

            verbose = kwargs.get("verbose", False)
            history = kwargs.get("history", "")

            response_text = api.send_query(prompt=prompt, verbose=verbose, HISTORY=history)

            return CompletionResponse(text=response_text)

        except Exception as e:
            logger.error(f"회사 LLM 호출 실패: {e}")
            return CompletionResponse(text=f"LLM 호출 실패: {str(e)}")

class RAGEngine:
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self.paper_dir = Config.PAPER_DIR
        self.index = None

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
            self.llm = CompanyLLM()
            logger.info(f"[LLM] 회사 LLM 사용 (Custom): {current_config['model']}")
        else:
            raise ValueError(f"지원하지 않는 LLM 타입: {llm_type}")

        Settings.llm = self.llm
        Settings.embed_model = HuggingFaceEmbedding(model_name=Config.EMBEDDING_MODEL)
        Settings.chunk_size = Config.CHUNK_SIZE
        Settings.chunk_overlap = Config.CHUNK_OVERLAP

    # _cleanup_orphan_md, convert_pdf_to_md, build_or_load_index, manual_rag_query, query 등 기존 함수 그대로

# 나머지 함수 (이전 답변과 동일하게 유지)
