# backend_dagster.py
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dagster import asset, job, schedule, Definitions, define_asset_job
from datetime import datetime
from core.paper_manager import PaperManager
from core.rag_engine import RAGEngine
from core.prompt_manager import PromptManager
from core.utils import save_to_history

@asset
def download_papers():
    print(f"[{datetime.now()}] 논문 다운로드 시작")
    manager = PaperManager()
    downloaded = manager.download_from_arxiv(max_results=30)
    manager.scan_user_added_papers()
    return downloaded

@asset
def build_rag_index(download_papers):
    print(f"[{datetime.now()}] RAG 인덱스 빌드 시작")
    engine = RAGEngine()
    engine.build_or_load_index()
    print(f"[{datetime.now()}] RAG 인덱스 빌드 완료")

@asset
def generate_daily_analysis(build_rag_index):
    print(f"[{datetime.now()}] 일일 분석 생성 시작")
    pm = PromptManager()
    analyses = {
        "tech_tree": pm.generate_analysis("tech_tree"),
        "trend_analysis": pm.generate_analysis("trend_analysis"),
        "challenges": pm.generate_analysis("challenges"),
        "open_source_summary": pm.generate_analysis("open_source_summary")
    }
    for analysis_type, content in analyses.items():
        save_to_history("daily_analysis", analysis_type, content)
    print(f"[{datetime.now()}] 일일 분석 생성 완료")

# 일일 업데이트 작업
daily_update_job = define_asset_job("daily_update_job", selection=["generate_daily_analysis"])

# 매일 오전 8시 스케줄
@schedule(cron_schedule="0 8 * * *", job=daily_update_job)
def daily_schedule():
    return {}

# Dagster 정의
defs = Definitions(
    assets=[download_papers, build_rag_index, generate_daily_analysis],
    jobs=[daily_update_job],
    schedules=[daily_schedule]
)