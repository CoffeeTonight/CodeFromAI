# scheduler.py (backend 또는 core 어디에든 놓을 수 있음)
import sys
from pathlib import Path
import time
from datetime import datetime
import schedule
import logging

# 프로젝트 루트 경로 자동 탐지 (backend 또는 core 어디든 OK)
current_file = Path(__file__).resolve()
if current_file.parent.name == "core":
    project_root = current_file.parent.parent  # core 안에 있을 때
else:
    project_root = current_file.parent.parent  # backend 안에 있을 때

sys.path.insert(0, str(project_root))

# core 모듈 import
from core.paper_manager import PaperManager
from core.rag_engine import RAGEngine
from core.prompt_manager import PromptManager
from core.utils import save_to_history
from core.config import Config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_papers():
    logger.info("1. 논문 처리 시작...")

    manager = PaperManager()
    manager.verify_and_cleanup_history(mode="auto")  # 의도적 삭제 존중

    if Config.SKIP_ARXIV_DOWNLOAD:
        logger.info("옵션 설정: arXiv 자동 다운로드 스킵 → 로컬 PDF만 분석")
        downloaded = 0
    else:
        logger.info("arXiv에서 새 논문 다운로드 시작...")
        downloaded = manager.download_from_arxiv(max_results=30)

    # 항상 로컬에 추가된 PDF 스캔 (사용자 직접 넣은 논문)
    manager.scan_user_added_papers()
    manager.generate_current_papers_snapshot()

    logger.info(f"{downloaded}개 새 논문 다운로드 완료 | 로컬 PDF 분석 모드: {'ON' if Config.SKIP_ARXIV_DOWNLOAD else 'OFF'}")
    return downloaded

def update_rag_index():
    logger.info("2. RAG 인덱스 빌드 시작...")
    engine = RAGEngine()
    result = engine.build_or_load_index()
    if result is None:
        logger.error("RAG 인덱스 빌드 실패")
    else:
        logger.info("RAG 인덱스 준비 완료")
    return result

def generate_analysis():
    logger.info("3. LLM 분석 생성 시작...")
    pm = PromptManager()

    analyses = {
        "tech_tree": pm.generate_analysis("tech_tree"),
        "trend_analysis": pm.generate_analysis("trend_analysis"),
        "challenges": pm.generate_analysis("challenges"),
        "open_source_summary": pm.generate_analysis("open_source_summary")
    }

    current_model = Config.SELECTED_MODEL
    for analysis_type, result in analyses.items():
        save_to_history(
            title="daily_analysis",
            entry_type=analysis_type,
            content=result,
            metadata={"note": f"Generated using {current_model}"}
        )

    logger.info(f"일일 분석 완료 (LLM: {current_model})")
    return analyses

def daily_update_job():
    logger.info("=== 일일 분석 업데이트 시작 ===")
    print(f"[시간] {datetime.now().astimezone()}")

    download_papers()
    update_rag_index()
    result = generate_analysis()

    logger.info("=== 일일 분석 업데이트 완료 ===\n")
    print("\n=== 분석 결과 요약 ===")
    for key, value in result.items():
        print(f"\n{key.upper()}:\n{str(value)[:500]}...")
    print("\n=== 완료 ===\n")

if __name__ == "__main__":
    print(f"스케줄러 시작 - 현재 시간: {datetime.now().astimezone()}")
    print("매일 오전 8시 (한국 시간)에 실행")
    print(f"arXiv 다운로드 모드: {'스킵 (로컬 PDF만 분석)' if Config.SKIP_ARXIV_DOWNLOAD else '활성화'}")

    schedule.every().day.at("08:00", "Asia/Seoul").do(daily_update_job)

    # 테스트용 즉시 실행 (필요할 때만 주석 해제)
    # daily_update_job()

    while True:
        schedule.run_pending()
        time.sleep(60)