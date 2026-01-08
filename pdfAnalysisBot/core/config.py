# core/config.py
import os
import platform
from pathlib import Path
from typing import Dict, Any
import logging
from datetime import datetime


class Config:
    SKIP_ARXIV_DOWNLOAD = False
    SELECTED_MODEL = "llama3.2:3b"

    USE_DSPY = False

    BASE_DIR = Path(__file__).parent.resolve()
    DB_DIR = BASE_DIR / ".db_pallm"

    PAPER_DIR = DB_DIR / "paper"
    DATA_DIR = DB_DIR / "data"
    HISTORY_DIR = DB_DIR / "history"

    DOWNLOAD_HISTORY_PATH = DB_DIR / "download_history.jsonl"
    OPEN_SOURCE_DB_PATH = DB_DIR / "open_source.jsonl"

    DEFAULT_ARXIV_QUERY = (
        '("large language model" OR LLM OR AI) AND '
        '(semiconductor OR design OR verification OR SoC OR UVM)'
    )

    CHUNK_SIZE = 1024
    CHUNK_OVERLAP = 200
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    @classmethod
    def toggle_arxiv_download(cls, value: bool):
        cls.SKIP_ARXIV_DOWNLOAD = value
        print(f"arXiv 다운로드 스킵 모드 변경: {value}")

    @staticmethod
    def get_ollama_base_url() -> str:
        system = platform.system()
        if system == "Windows":
            url = "http://localhost:11434"
        elif system == "Linux":
            if "microsoft" in platform.uname().release.lower():
                url = "http://host.docker.internal:11434"
            else:
                url = "http://localhost:11434"
        else:
            url = "http://localhost:11434"
        return url

    LLM_MODELS: Dict[str, Dict[str, Any]] = {
        "llama3.2:3b": {
            "name": "Llama3.2 3B (Ollama)",
            "model": "llama3.2:3b",
            "type": "ollama",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "max_tokens": 2048,
            "timeout": 1200.0
        },
        "qwen3:32b": {
            "name": "Qwen3 32B (Ollama)",
            "model": "qwen3:32b",
            "type": "ollama",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "max_tokens": 4096,
            "timeout": 600.0
        },
        "qwen2:7b": {
            "name": "Qwen2 7B (Ollama)",
            "model": "qwen2:7b",
            "type": "ollama",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "max_tokens": 2048,
            "timeout": 180.0
        },
        "phi3:medium": {
            "name": "Phi-3 Medium (Ollama)",
            "model": "phi3:medium",
            "type": "ollama",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "max_tokens": 2048,
            "timeout": 240.0
        },
        "company_llm": {
            "name": "회사 내부 LLM (Internal)",
            "model": "gpt-4o-company-v1",
            "type": "openai_compatible",
            "api_url": "https://llm-gateway.company.com/v1/chat/completions",
            "api_key": os.getenv("COMPANY_LLM_API_KEY", "your-api-key-here"),
            "user_key": os.getenv("COMPANY_LLM_USER_KEY", "your-user-key-here"),
            "cert_path": str(BASE_DIR / "certs" / "company_root_ca.pem"),
            "verify_ssl": True,
            "lce": True,
            "context_length": 32768,
            "temperature": 0.3,
            "max_tokens": 8192,
            "timeout": 180
        }
    }

    @classmethod
    def get_current_llm_config(cls) -> Dict[str, Any]:
        if cls.SELECTED_MODEL not in cls.LLM_MODELS:
            logger.warning(f"선택된 모델 '{cls.SELECTED_MODEL}' 없음 → 기본값으로 변경")
            cls.SELECTED_MODEL = "llama3.2:3b"

        config = cls.LLM_MODELS[cls.SELECTED_MODEL].copy()

        if config.get("type") == "ollama":
            config["api_base"] = cls.get_ollama_base_url()

        print(f"현재 LLM 설정 로드: {cls.SELECTED_MODEL}")
        return config

    @classmethod
    def get_available_models(cls) -> list:
        models = list(cls.LLM_MODELS.keys())
        logger.debug(f"사용 가능한 모델 목록: {models}")
        return models

    # arXiv 설정
    ARXIV_MAX_RESULTS = 50
    ARXIV_SORT_BY = "relevance"
    ARXIV_SORT_ORDER = "descending"
    ARXIV_USE_LIB = False

    @classmethod
    def set_arxiv_sort(cls, sort_by: str, sort_order: str = "descending"):
        valid_sort_by = ["submitted_date", "last_updated_date", "relevance"]
        valid_order = ["ascending", "descending"]
        if sort_by not in valid_sort_by:
            raise ValueError(f"sort_by는 {valid_sort_by} 중 하나여야 합니다.")
        if sort_order not in valid_order:
            raise ValueError(f"sort_order는 {valid_order} 중 하나여야 합니다.")
        cls.ARXIV_SORT_BY = sort_by
        cls.ARXIV_SORT_ORDER = sort_order
        print(f"arXiv 정렬 변경: {sort_by} ({sort_order})")

    @classmethod
    def set_arxiv_use_lib(cls, value: bool):
        cls.ARXIV_USE_LIB = value
        print(f"arXiv 다운로드 방식 변경: {'명시적 RSS' if not value else 'arxiv 라이브러리'}")

    # 논문 점수 가중치
    PAPER_SCORE_WEIGHTS = {
        "latest": 40,
        "citation": 30,
        "similarity": 20,
        "implementation": 10
    }

    @classmethod
    def set_paper_weights(cls, latest: int, citation: int, similarity: int, implementation: int):
        total = latest + citation + similarity + implementation
        if total == 0:
            raise ValueError("가중치 합계는 0이 될 수 없습니다.")
        cls.PAPER_SCORE_WEIGHTS = {
            "latest": latest,
            "citation": citation,
            "similarity": similarity,
            "implementation": implementation
        }
        print(f"논문 평가 가중치 변경: {cls.PAPER_SCORE_WEIGHTS}")

    # 서브폴더 경로
    ARXIV_PAPER_DIR = PAPER_DIR / "arxiv"
    SEMANTIC_PAPER_DIR = PAPER_DIR / "semantic"
    CONFERENCE_PAPER_DIR = PAPER_DIR / "conference"
    USER_PAPER_DIR = PAPER_DIR / "user"

    ARXIV_DATA_DIR = DATA_DIR / "arxiv"
    SEMANTIC_DATA_DIR = DATA_DIR / "semantic"
    CONFERENCE_DATA_DIR = DATA_DIR / "conference"
    USER_DATA_DIR = DATA_DIR / "user"

    @classmethod
    def init_directories(cls):
        dirs_to_create = [
            cls.ARXIV_PAPER_DIR, cls.SEMANTIC_PAPER_DIR,
            cls.CONFERENCE_PAPER_DIR, cls.USER_PAPER_DIR,
            cls.ARXIV_DATA_DIR, cls.SEMANTIC_DATA_DIR,
            cls.CONFERENCE_DATA_DIR, cls.USER_DATA_DIR
        ]
        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)

# 초기화 실행
Config.init_directories()

# 테스트
if __name__ == "__main__":
    print("=== Config 테스트 시작 ===")
    print(f"현재 환경: {platform.system()}")
    print(f"Ollama URL: {Config.get_ollama_base_url()}")
    print(f"사용 가능한 모델: {Config.get_available_models()}")
    print(f"현재 모델: {Config.SELECTED_MODEL}")
    print("테스트 완료!")