import time
from datetime import datetime
from paper_manager import PaperManager
from rag_engine import RAGEngine
from prompt_manager import PromptManager
from utils import save_to_history
import logging
import schedule
from config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def download_papers():
    manager = PaperManager()
    manager.verify_and_cleanup_history(mode="auto")  # 의도적 삭제 존중
    downloaded = manager.download_from_arxiv(max_results=30)
    manager.scan_user_added_papers()

    # 매일 실행 끝날 때 현재 상태 스냅샷 저장
    manager.generate_current_papers_snapshot()
    logger.info(f"{downloaded}개 새 논문 다운로드 및 사용자 추가 논문 스캔 완료")
    return downloaded


def update_rag_index():
    logger.info("Update RAG Index 시작")
    engine = RAGEngine()
    query_engine = engine.build_or_load_index()
    logger.info("RAG 인덱스 업데이트 완료")
    return query_engine


def generate_analysis():
    logger.info("Generate Daily Analysis 시작")
    pm = PromptManager()

    analyses = {
        "tech_tree": pm.generate_analysis("tech_tree"),
        "trend_analysis": pm.generate_analysis("trend_analysis"),
        "challenges": pm.generate_analysis("challenges"),
        "open_source_summary": pm.generate_analysis("open_source_summary")
    }

    current_model = Config.SELECTED_MODEL  # 명시적으로 가져와서 기록

    # 히스토리 저장 (llm_model 자동 포함)
    for analysis_type, result in analyses.items():
        save_to_history(
            title="daily_analysis",
            entry_type=analysis_type,
            content=result,
            metadata={"note": f"Generated using {current_model}"}
        )

    logger.info(f"일일 분석 완료 - 히스토리에 저장됨 (LLM: {current_model})")
    return analyses


def daily_update_job():
    logger.info("=== 일일 RAG 업데이트 시작 ===")

    download_papers()
    update_rag_index()
    result = generate_analysis()

    logger.info("=== 일일 RAG 업데이트 완료 ===")

    # 결과 요약 출력 (테스트용)
    print("\n=== 일일 분석 결과 요약 ===")
    for key, value in result.items():
        print(f"\n{key.upper()}:\n{str(value)[:500]}...")
    print("=== 완료 ===\n")


if __name__ == "__main__":
    print(f"현재 시간: {datetime.now().astimezone()}")
    print("일일 업데이트 스케줄러 시작 (매일 오전 8시 한국 시간)")

    # 매일 오전 8시 실행 (한국 시간)
    schedule.every().day.at("08:00", "Asia/Seoul").do(daily_update_job)

    # 테스트를 위해 즉시 한 번 실행하고 싶다면 아래 줄 주석 해제
    daily_update_job()

    while True:
        schedule.run_pending()
        time.sleep(60)  # 1분마다 체크