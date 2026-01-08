# backend/scheduler.py (backend 또는 core 어디에든 놓을 수 있음)
import sys
from pathlib import Path
import time
from datetime import datetime
import schedule

# 프로젝트 루트 경로 자동 탐지
current_file = Path(__file__).resolve()
if current_file.parent.name == "core":
    project_root = current_file.parent.parent
else:
    project_root = current_file.parent.parent

sys.path.insert(0, str(project_root))

# core 모듈 import
from core.paper_manager import PaperManager
from core.rag_engine import RAGEngine
from core.prompt_manager import PromptManager
from core.utils import save_to_history
from core.config import Config
from core.utils import get_logger  # 중앙 로거 사용

# 로거 설정 (모듈별 이름으로 구분)
logger = get_logger("Scheduler")

def download_papers():
    logger.info("1. 논문 처리 시작...")
    manager = PaperManager()
    manager.verify_and_cleanup_history(mode="auto")  # 의도적 삭제 존중

    if Config.SKIP_ARXIV_DOWNLOAD:
        logger.info("옵션: arXiv 자동 다운로드 스킵 → 로컬 PDF만 분석")
        downloaded = 0
    else:
        logger.info("arXiv에서 새 논문 다운로드 시작 (목표 30개 유지)")
        downloaded = manager.download_from_arxiv(target_count=30)

    # 사용자 추가 논문 스캔 + 스냅샷
    manager.scan_user_added_papers()
    manager.generate_current_papers_snapshot()

    total_now = len(list(Config.PAPER_DIR.glob("*.pdf")))
    logger.info(f"{downloaded}개 새 논문 다운로드 완료 → 현재 총 {total_now}개 보유")
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
    logger.info(f"[시간] {datetime.now().astimezone()}")

    download_papers()
    update_rag_index()
    result = generate_analysis()

    logger.info("=== 일일 분석 업데이트 완료 ===")

    logger.info("\n=== 분석 결과 요약 ===")
    for key, value in result.items():
        logger.info(f"\n{key.upper()}:\n{str(value)[:500]}...")
    logger.info("\n=== 완료 ===\n")

if __name__ == "__main__":
    logger.info(f"스케줄러 시작 - 현재 시간: {datetime.now().astimezone()}")
    logger.info("매일 오전 8시 (한국 시간)에 실행")
    logger.info(f"arXiv 다운로드 모드: {'스킵 (로컬 PDF만 분석)' if Config.SKIP_ARXIV_DOWNLOAD else '활성화 (목표 30개 유지)'}")

    schedule.every().day.at("08:00", "Asia/Seoul").do(daily_update_job)

    # 테스트용 즉시 실행 (필요시 주석 해제)
    daily_update_job()

    while True:
        schedule.run_pending()
        time.sleep(60)