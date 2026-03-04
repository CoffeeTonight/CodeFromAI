from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import MessagesState

class VerifClawState(MessagesState):
    """VerifClaw의 모든 상태를 관리하는 TypedDict"""
    task: str                          # 현재 작업 ("poll_regression", "analyze_coverage" 등)
    coverage_db_path: str
    current_coverage: float
    last_hole_analysis: str
    pending_forcing: List[Dict]        # 실시간 forcing 대기열
    kg_query_result: List[Dict]        # KG 검색 결과
    llm_response: str                  # LLM 최종 응답
    human_approval_needed: bool