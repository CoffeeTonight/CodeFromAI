# core/config.py  (또는 config.py)
import os
import platform
from pathlib import Path
from typing import Dict, Any

class Config:
    # 현재 선택된 모델 (Streamlit에서 변경 가능)
    SELECTED_MODEL = "llama3.2:3b"  # 기본값: 빠른 테스트용

    # DSPy 사용 여부 (기본값: False - 안정성 우선)
    USE_DSPY = False

    # 프로젝트 루트 경로
    BASE_DIR = Path(__file__).parent.resolve()
    DB_DIR = BASE_DIR / ".db_pallm"

    # 폴더 경로
    PAPER_DIR = DB_DIR / "papers"
    DATA_DIR = DB_DIR / "data"
    HISTORY_DIR = DB_DIR / "history"

    # 파일 경로
    DOWNLOAD_HISTORY_PATH = DB_DIR / "download_history.jsonl"
    OPEN_SOURCE_DB_PATH = DB_DIR / "open_source.jsonl"

    # arXiv 기본 쿼리
    DEFAULT_ARXIV_QUERY = (
        '("large language model" OR LLM OR AI OR agent OR reasoning) AND '
        '(semiconductor OR design OR verification OR SoC OR UVM OR FPGA OR ASIC)'
    )

    # RAG 설정
    CHUNK_SIZE = 1024
    CHUNK_OVERLAP = 200
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384차원

    # 실행 환경에 따른 Ollama URL 자동 결정
    @staticmethod
    def get_ollama_base_url() -> str:
        system = platform.system()
        if system == "Windows":
            return "http://localhost:11434"
        elif system == "Linux":
            # WSL 환경 감지
            if "microsoft" in platform.uname().release.lower():
                return "http://host.docker.internal:11434"
            else:
                return "http://localhost:11434"
        else:
            return "http://localhost:11434"

    # LLM 모델 옵션 (이름: 설정 딕셔너리)
    LLM_MODELS: Dict[str, Dict[str, Any]] = {
        "llama3.2:3b": {
            "model": "llama3.2:3b",
            "description": "빠른 테스트용 (3B, 초고속 응답)",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "timeout": 1200.0
        },
        "qwen3:32b": {
            "model": "qwen3:32b",
            "description": "고품질 분석용 (32B, 정확도 최고)",
            "api_base": get_ollama_base_url(),
            "temperature": 0.1,
            "timeout": 1800.0
        },
        "qwen2:7b": {
            "model": "qwen2:7b",
            "description": "균형형 (7B, 속도와 품질 균형)",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "timeout": 600.0
        },
        "phi3:medium": {
            "model": "phi3:medium",
            "description": "Microsoft 코딩 특화 (14B)",
            "api_base": get_ollama_base_url(),
            "temperature": 0.3,
            "timeout": 900.0
        }
    }

    @classmethod
    def get_current_llm_config(cls) -> Dict[str, Any]:
        """현재 선택된 모델의 설정 반환"""
        if cls.SELECTED_MODEL not in cls.LLM_MODELS:
            cls.SELECTED_MODEL = "llama3.2:3b"  # fallback
        config = cls.LLM_MODELS[cls.SELECTED_MODEL].copy()
        config["api_base"] = cls.get_ollama_base_url()  # 항상 최신 URL 적용
        return config

    @classmethod
    def init_directories(cls):
        for dir_path in [cls.DB_DIR, cls.PAPER_DIR, cls.DATA_DIR, cls.HISTORY_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # 히스토리 파일 초기화
        if not cls.DOWNLOAD_HISTORY_PATH.exists():
            cls.DOWNLOAD_HISTORY_PATH.touch()

        if not cls.OPEN_SOURCE_DB_PATH.exists():
            cls.OPEN_SOURCE_DB_PATH.touch()

# 초기화 실행
Config.init_directories()

# 테스트용
if __name__ == "__main__":
    print("현재 환경:", platform.system())
    print("Ollama URL:", Config.get_ollama_base_url())
    print("현재 모델:", Config.SELECTED_MODEL)
    print("설정:", Config.get_current_llm_config())