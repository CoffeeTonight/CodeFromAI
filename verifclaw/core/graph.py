from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from core.state import VerifClawState
from memory.kg_memory import VerifClawMemory

# ------------------ 메모리 초기화 ------------------
memory = VerifClawMemory()
checkpointer = MemorySaver()

# ------------------ 노드 (스킬) ------------------
async def spec_parser_node(state: VerifClawState):
    print("[NODE] Spec Parser 실행 중...")
    return {"task": "coverage_analyzer"}

async def coverage_analyzer_node(state: VerifClawState):
    print("[NODE] Coverage Analyzer 실행 중...")
    results = memory.search("coverage hole")
    return {"kg_query_result": results, "task": "forcing_decision"}

async def forcing_decision_node(state: VerifClawState):
    print("[NODE] Forcing Decision 실행 중...")
    return {"pending_forcing": [{"signal": "AWLEN", "value": "255"}], "task": "dpi_forcing"}

async def dpi_forcing_node(state: VerifClawState):
    print("[NODE] DPI Forcing 실행 중...")
    from skills.dpi_socket_master import dpi_socket_master
    await dpi_socket_master(state.get("pending_forcing", []))
    return {"task": "done"}

# ------------------ 그래프 구축 ------------------
workflow = StateGraph(VerifClawState)

workflow.add_node("spec_parser", spec_parser_node)
workflow.add_node("coverage_analyzer", coverage_analyzer_node)
workflow.add_node("forcing_decision", forcing_decision_node)
workflow.add_node("dpi_forcing", dpi_forcing_node)

workflow.set_entry_point("spec_parser")
workflow.add_edge("spec_parser", "coverage_analyzer")
workflow.add_edge("coverage_analyzer", "forcing_decision")
workflow.add_edge("forcing_decision", "dpi_forcing")
workflow.add_edge("dpi_forcing", END)

verifclaw_graph = workflow.compile(checkpointer=checkpointer)

print("✅ VerifClaw LangGraph 초기화 완료 (Persistent Agentic Workflow)")