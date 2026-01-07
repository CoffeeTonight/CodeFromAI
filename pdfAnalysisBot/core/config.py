# core/config.py
import os
import platform
from pathlib import Path
from typing import Dict, Any

class Config:
    SKIP_ARXIV_DOWNLOAD = False  # True로 하면 arXiv 다운로드 완전 스킵
    # 현재 선택된 모델 (Streamlit에서 변경 가능)
    SELECTED_MODEL = "llama3.2:3b"  # 기본값: 빠른 테스트용 (안전)

    # DSPy 사용 여부
    USE_DSPY = False

    # 프로젝트 루트 경로
    BASE_DIR = Path(__file__).parent.resolve()
    DB_DIR = BASE_DIR / ".db_pallm"

    # 폴더 경로
    PAPER_DIR = DB_DIR / "paper"
    DATA_DIR = DB_DIR / "data"
    HISTORY_DIR = DB_DIR / "history"

    # 파일 경로
    DOWNLOAD_HISTORY_PATH = DB_DIR / "download_history.jsonl"
    OPEN_SOURCE_DB_PATH = DB_DIR / "open_source.jsonl"

    # arXiv 기본 쿼리
    DEFAULT_ARXIV_QUERY = (
        '("large language model" OR LLM OR AI) AND '
        '(semiconductor OR design OR verification OR SoC OR UVM)'
    )

    # RAG 설정
    CHUNK_SIZE = 1024
    CHUNK_OVERLAP = 200
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    @classmethod
    def toggle_arxiv_download(cls, value: bool):
        cls.SKIP_ARXIV_DOWNLOAD = value

    # 실행 환경에 따른 Ollama URL 자동 결정
    @staticmethod
    def get_ollama_base_url() -> str:
        system = platform.system()
        if system == "Windows":
            return "http://localhost:11434"
        elif system == "Linux":
            if "microsoft" in platform.uname().release.lower():  # WSL2
                return "http://host.docker.internal:11434"
            else:
                return "http://localhost:11434"
        else:
            return "http://localhost:11434"

    # LLM 모델 옵션 (이름: 설정 딕셔너리)
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
        # ==================== 회사 내부 LLM ====================
        "company_llm": {
            "name": "회사 내부 LLM (Internal)",
            "model": "gpt-4o-company-v1",  # 회사에서 지정한 모델명
            "type": "openai_compatible",   # OpenAI 스타일 API
            "api_url": "https://llm-gateway.company.com/v1/chat/completions",
            "api_key": os.getenv("COMPANY_LLM_API_KEY", "your-api-key-here"),  # 환경변수 우선
            "user_key": os.getenv("COMPANY_LLM_USER_KEY", "your-user-key-here"),
            "cert_path": str(BASE_DIR / "certs" / "company_root_ca.pem"),  # 필요 시
            "verify_ssl": True,        # False로 하면 인증서 무시 (테스트용)
            "lce": True,               # License Check Enforcement
            "context_length": 32768,   # 회사 LLM 컨텍스트 길이
            "temperature": 0.3,
            "max_tokens": 8192,
            "timeout": 180
        }
    }

    @classmethod
    def get_current_llm_config(cls) -> Dict[str, Any]:
        """현재 선택된 모델의 설정 반환"""
        if cls.SELECTED_MODEL not in cls.LLM_MODELS:
            print(f"[경고] 선택된 모델 '{cls.SELECTED_MODEL}' 없음 → 기본값으로 변경")
            cls.SELECTED_MODEL = "llama3.2:3b"

        config = cls.LLM_MODELS[cls.SELECTED_MODEL].copy()

        # Ollama 모델은 항상 최신 URL 적용
        if config.get("type") == "ollama":
            config["api_base"] = cls.get_ollama_base_url()

        return config

    @classmethod
    def get_available_models(cls) -> list:
        """Streamlit에서 모델 선택 드롭다운용"""
        return [key for key in cls.LLM_MODELS.keys()]

    @classmethod
    def init_directories(cls):
        for dir_path in [cls.DB_DIR, cls.PAPER_DIR, cls.DATA_DIR, cls.HISTORY_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # 히스토리 파일 초기화
        if not cls.DOWNLOAD_HISTORY_PATH.exists():
            cls.DOWNLOAD_HISTORY_PATH.touch()

        if not cls.OPEN_SOURCE_DB_PATH.exists():
            cls.OPEN_SOURCE_DB_PATH.touch()

    # arXiv 정렬 기준 설정
    ARXIV_MAX_RESULTS = 50
    ARXIV_SORT_BY = "relevance"  # "submitted_date", "last_updated_date", "relevance" 중 선택
    ARXIV_SORT_ORDER = "descending"  # "ascending" 또는 "descending"

    # Streamlit에서 변경 쉽게 하기 위한 메서드
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

# 초기화 실행
Config.init_directories()

# 테스트
if __name__ == "__main__":
    print("현재 환경:", platform.system())
    print("Ollama URL:", Config.get_ollama_base_url())
    print("사용 가능한 모델:", Config.get_available_models())
    print("현재 모델:", Config.SELECTED_MODEL)
    print("설정:", Config.get_current_llm_config())