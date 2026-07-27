"""env_flow — replay top commands / paradigm for VERIF-CPU-SOC."""

from __future__ import annotations

from pathlib import Path

from soc_verify.env_flow import analyze_verification_flow, flow_to_toy_requirements
from soc_verify.toy_intake import resolve_toy_intake

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "VERIF-CPU-SOC"


def test_flow_replay_verif_cpu_is_cpu_fw():
    rtl = Path("/home/user/tools/__CFI/VerifCPU/verif_cpu_verilog")
    if not rtl.is_dir():
        # fallback from project discovered
        from soc_verify.env_analyze import _rtl_root_from_project

        rtl = _rtl_root_from_project(PROJECT)
    flow = analyze_verification_flow(PROJECT, rtl_root=rtl)
    assert flow["contract"] == "env_flow_v1"
    assert flow["steps"], "expected verification_sequence steps"
    assert flow["paradigm"]["primary"] == "cpu_fw"
    tools = set(flow["tools"])
    assert "python" in tools or "make" in tools or "example.sh" in tools
    # first gate should surface example.sh gen style command from ops
    cmds = [" ".join(c) for c in sum((s["commands"] for s in flow["steps"]), [])]
    joined = " | ".join(cmds)
    assert "example.sh" in joined or "gen" in joined or flow["example_sh"].get("present")


def test_flow_to_toy_requirements_cpu_fw():
    rtl = Path("/home/user/tools/__CFI/VerifCPU/verif_cpu_verilog")
    flow = analyze_verification_flow(PROJECT, rtl_root=rtl if rtl.is_dir() else None)
    req = flow_to_toy_requirements(flow)
    assert req["paradigm"] == "cpu_fw"
    assert req["required_artifacts"]
    assert "example.sh" in req["required_artifacts"] or req["gen_entry"]


def test_resolve_toy_intake_embeds_flow():
    spec = resolve_toy_intake(ROOT, source_id="VERIF-CPU-SOC")
    assert spec.paradigm == "cpu_fw"
    assert spec.top_commands or spec.gen_entry
    assert spec.flow_summary
