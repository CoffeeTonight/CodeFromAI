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
            context_window=32768,
            num_output=8192
        )

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """non-streaming (fallback)"""
        # 스트리밍 generator에서 첫 번째 결과만 가져오기
        stream_gen = self.stream_complete(prompt, **kwargs)
        full_text = ""
        for resp in stream_gen:
            full_text += resp.text
        return CompletionResponse(text=full_text)

    def stream_complete(self, prompt: str, **kwargs):
        """회사 API의 send_query 스트리밍 연결"""
        try:
            from company_api import CompanyAPI  # 회사 제공 모듈

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

            # send_query가 generator 반환한다고 가정
            for token in api.send_query(prompt=prompt, verbose=verbose, HISTORY=history):
                yield CompletionResponse(text=token)

        except Exception as e:
            logger.error(f"회사 LLM 스트리밍 실패: {e}")
            yield CompletionResponse(text=f"스트리밍 실패: {str(e)}")

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
