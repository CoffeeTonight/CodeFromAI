from __future__ import annotations

from pathlib import Path

from soc_verify.graph_llm_bridge import build_graph_llm_payload


ROOT = Path(__file__).resolve().parents[1]


def test_graph_llm_payload_slices_flow_spec() -> None:
    payload = build_graph_llm_payload(
        root=ROOT,
        session_id="sess1",
        graph_id="verify_group",
        node_id="run_gate",
        state_snapshot={"project_id": "EXAMPLE-SOC", "stage": "simulation", "group": "gpio_ext"},
    )
    assert payload["contract"] == "langgraph_flow_driver"
    fs = payload["flow_spec"]
    assert "graphs" in fs
    assert list(fs["graphs"].keys()) == ["verify_group"]
    assert "orchestrator" not in fs.get("graphs", {})
    assert payload["current"]["node"] == "run_gate"