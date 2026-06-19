from __future__ import annotations

from soc_verify.graphs.child_subgraphs import build_promote_child_graph, build_runner_loop_child_graph


def test_promote_child_graph_happy_path():
    g = build_promote_child_graph()
    out = g.invoke({"trust_ok": True, "promote_decision_ok": True})
    assert out.get("crystallize_ok") is True


def test_runner_loop_child_stops_on_parity():
    g = build_runner_loop_child_graph()
    out = g.invoke({"parity_ok": True, "codegen_round": 0, "max_rounds": 10})
    assert out.get("parity_ok") is True
    assert int(out.get("codegen_round", 0)) == 0