# backend_pipeline/backend_python.py
import sys, os
from pathlib import Path
import traceback

# 프로젝트 루트 경로 추가 (import 오류 방지)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

print(f"[DEBUG] 프로젝트 루트 경로 추가: {project_root}")
print(f"[DEBUG] sys.path[0]: {sys.path[0]}")

from datetime import datetime
from core.paper_manager import PaperManager
from core.rag_engine import RAGEngine
from core.prompt_manager import PromptManager
from core.utils import save_to_history
from core.config import Config  # 기본 키워드 사용

def daily_update():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 일일 분석 업데이트 시작 ===")

    success = True

    try:
        # 1. 논문 다운로드
        print("1. 논문 다운로드 시작...")
        manager = PaperManager()

        # 환경 변수에서 사용자 키워드 가져오기 (Streamlit에서 전달)
        custom_query = os.getenv("CUSTOM_ARXIV_QUERY")
        if custom_query:
            downloaded = manager.download_from_arxiv_rss(query=custom_query, max_results=30)
        else:
            downloaded = manager.download_from_arxiv_rss(max_results=30)  # 기본
        # 방법 2: 환경 변수로 사용자 키워드 전달 (고급 - 선택)
        # custom_query = os.getenv("CUSTOM_ARXIV_QUERY")
        # if custom_query:
        #     downloaded = manager.download_from_arxiv_rss(query=custom_query, max_results=30)
        # else:
        #     downloaded = manager.download_from_arxiv_rss(max_results=30)

        scanned = manager.scan_user_added_papers()
        print(f"1. 완료: 새 논문 {downloaded}개, 사용자 추가 {scanned}개 처리")

    except Exception as e:
        print(f"1. 논문 다운로드 실패: {e}")
        traceback.print_exc()
        success = False

    try:
        # 2. RAG 인덱스 빌드
        print("2. RAG 인덱스 빌드 시작...")
        engine = RAGEngine()
        result = engine.build_or_load_index()
        if result:
            print("2. RAG 인덱스 빌드/로드 성공")
        else:
            print("2. RAG 인덱스 빌드 실패")
            success = False

    except Exception as e:
        print(f"2. RAG 인덱스 빌드 중 오류: {e}")
        traceback.print_exc()
        success = False

    try:
        # 3. LLM 분석 생성
        print("3. LLM 분석 생성 시작...")
        pm = PromptManager()
        analyses = {
            "tech_tree": pm.generate_analysis("tech_tree"),
            "trend_analysis": pm.generate_analysis("trend_analysis"),
            "challenges": pm.generate_analysis("challenges"),
            "open_source_summary": pm.generate_analysis("open_source_summary")
        }

        # 히스토리 저장
        print("4. 분석 결과 히스토리 저장 시작...")
        for analysis_type, content in analyses.items():
            try:
                save_to_history("daily_analysis", analysis_type, content or "내용 없음")
                print(f"4. {analysis_type} 저장 성공")
            except Exception as save_e:
                print(f"4. {analysis_type} 저장 실패: {save_e}")
                traceback.print_exc()
                success = False

        if success:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 일일 분석 업데이트 성공적으로 완료 ===")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 일일 분석 업데이트 부분 실패 (일부 단계 오류) ===")

    except Exception as e:
        print(f"3. LLM 분석 중 오류: {e}")
        traceback.print_exc()
        success = False

    return success

if __name__ == "__main__":
    daily_update()