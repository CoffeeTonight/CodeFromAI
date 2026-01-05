# core/backend_prefect.py
import os
import sys
from pathlib import Path

# === 핵심: 프로젝트 루트 경로를 sys.path에 추가 ===
# scheduler.py가 core 폴더 안에 있으므로, 상위 폴더를 모듈 경로로 추가
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

# Prefect DB 경로 설정
prefect_home = project_root / "prefect_data"  # .prefect 대신 별도 폴더 추천
prefect_home.mkdir(parents=True, exist_ok=True)
os.environ["PREFECT_HOME"] = str(prefect_home)

from prefect import flow, task, get_run_logger
from datetime import datetime

# 이제 core 내부 모듈 정상 import
from core.paper_manager import PaperManager
from core.rag_engine import RAGEngine
from core.prompt_manager import PromptManager
from core.utils import save_to_history
from config import Config


@task(name="Download New Papers")
def download_papers_task():
    logger = get_run_logger()
    manager = PaperManager()
    downloaded = manager.download_from_arxiv(max_results=30)
    manager.scan_user_added_papers()
    logger.info(f"{downloaded}개 새 논문 다운로드 및 사용자 추가 논문 스캔 완료")
    return downloaded


@task(name="Update RAG Index")
def update_rag_index_task():
    logger = get_run_logger()
    engine = RAGEngine()
    query_engine = engine.build_or_load_index()
    logger.info("RAG 인덱스 업데이트 완료")
    return query_engine


@task(name="Generate Daily Analysis")
def generate_analysis_task():
    logger = get_run_logger()
    logger.info("=== LLM 분석 시작 ===")

    pm = PromptManager()

    analyses = {
        "tech_tree": pm.generate_analysis("tech_tree"),
        "trend_analysis": pm.generate_analysis("trend_analysis"),
        "challenges": pm.generate_analysis("challenges"),
        "open_source_summary": pm.generate_analysis("open_source_summary")
    }

    # 히스토리 저장
    for analysis_type, result in analyses.items():
        save_to_history(
            title="daily_analysis",
            entry_type=analysis_type,
            content=result
        )

    logger.info("=== LLM 분석 완료 - 히스토리에 저장됨 ===")
    return analyses

@flow(name="Daily Paper RAG Update Flow")
def daily_update_flow():
    logger = get_run_logger()
    logger.info("=== 일일 RAG 업데이트 플로우 시작 ===")

    download_papers_task()
    update_rag_index_task()
    result = generate_analysis_task()

    logger.info("=== 일일 RAG 업데이트 플로우 완료 ===")
    return result


# __main__ 테스트 및 자동 스케줄링
if __name__ == "__main__":
    print("=== Prefect Flow 테스트 시작 ===")
    result = daily_update_flow()

    print("\n=== 일일 분석 결과 요약 ===")
    for key, value in result.items():
        print(f"\n{key.upper()}:\n{str(value)[:500]}...")

    print("\n=== 테스트 완료 ===")

    print("\n자동 스케줄링 설정 중...")
    daily_update_flow.serve(
        name="daily-paper-rag-update",
        cron="0 8 * * *",  # 매일 오전 8시
        tags=["rag", "daily", "semiconductor"],
        description="매일 반도체 LLM 논문 업데이트 및 분석"
    )