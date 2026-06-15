from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from soc_verify.acquisition import (
    should_refresh_intake,
    should_refresh_project_search,
    workspace_acquisition_status,
)
from soc_verify.completeness import CompletenessMetrics
from soc_verify.config import load_user_config
from soc_verify.loop_guard import build_signature, record_failure
from soc_verify.models import load_yaml
from soc_verify.preflight import preflight_group, preflight_project
from soc_verify.stages import find_group_dir, resolve_group_script, verification_group_dir
from soc_verify.tag_cache import apply_tag_replace, should_refresh_tag
from soc_verify.trust_eval import select_runner, update_trust_after_run


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_preflight_example_ok():
    gaps = preflight_project(EXAMPLE)
    assert gaps == []


def test_acquisition_dates_and_schedule_due():
    config = load_user_config(ROOT)
    registry = load_yaml(ROOT / "registry" / "active_projects.yaml")
    discovered = load_yaml(EXAMPLE / "discovered.yaml")

    assert str(registry["acquisition"]["project_search"]["fetched_at"])[:10] == "2026-06-13"
    assert str(discovered["intake"]["fetched_at"])[:10] == "2026-06-01"
    assert not should_refresh_project_search(registry, config, today=date(2026, 6, 15))
    assert should_refresh_project_search(registry, config, today=date(2026, 6, 21))
    assert not should_refresh_intake(discovered, config, today=date(2026, 6, 20))

    ws = workspace_acquisition_status(ROOT, config, today=date(2026, 6, 14))
    assert ws["project_search"]["fetched_at"] == "2026-06-13"  # isoformat from acquisition module
    assert "EXAMPLE-SOC" in ws["projects"]


def test_stage_paths_and_preflight():
    sim_dir = verification_group_dir(EXAMPLE, "simulation", "gpio_ext")
    assert sim_dir.is_dir()
    assert find_group_dir(EXAMPLE, "simulation", "gpio_ext") == sim_dir
    assert preflight_group(sim_dir, EXAMPLE) == []

    script = resolve_group_script(EXAMPLE, "simulation", "gpio_ext")
    assert script is not None
    assert script == EXAMPLE / "ops" / "simulation" / "gpio_ext.py"


def test_tag_always_replace_invalidates_sanity():
    apply_tag_replace(EXAMPLE, "v1.0.0", today=date(2026, 6, 9))
    cache = apply_tag_replace(EXAMPLE, "v1.0.1", today=date(2026, 6, 13))
    assert cache["tag"]["value"] == "v1.0.1"
    assert cache["tag"]["replace_decision"] == "replace"
    assert cache["sanity"]["last_verdict"] is None


def test_trust_degrades_then_llm_runner():
    script = "test_script.py"
    update_trust_after_run(EXAMPLE, script, passed=False, one_shot=False)
    update_trust_after_run(EXAMPLE, script, passed=False, one_shot=False)
    update_trust_after_run(EXAMPLE, script, passed=False, one_shot=False)
    assert select_runner(EXAMPLE, script, 0.75) == "llm"


def test_low_completeness_forces_llm_even_if_trust_high():
    script = "gpio_ext.py"
    assert select_runner(EXAMPLE, script, 0.75, completeness=0.5, tau_completeness=0.75) == "llm"
    assert select_runner(EXAMPLE, script, 0.75, completeness=0.90, tau_completeness=0.75) == "python"


def test_loop_guard_stalemate():
    import uuid

    run_dir = EXAMPLE / "runs" / f"test-stale-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    sig = build_signature(gate="g", error_code="1", log_line="same error")
    state = record_failure(run_dir, sig)
    assert not state.stalemate
    state = record_failure(run_dir, sig)
    assert not state.stalemate
    state = record_failure(run_dir, sig)
    assert state.stalemate
    assert state.force_mode == "llm_full"


def test_completeness_policy_jira_withhold():
    from soc_verify.completeness import CompletenessMetrics, evaluate_completeness_policy

    m = CompletenessMetrics.from_events(
        {"gates_run": 5, "tool_incidents": 2, "llm_fix_rounds": 4, "fix_rounds": 4}
    )
    policies = {
        "completeness": {
            "thresholds": {
                "jira_complete_min": 0.80,
                "promote_min": 0.85,
                "promote_max_t": 0.10,
                "promote_max_l": 0.15,
            }
        }
    }
    d = evaluate_completeness_policy(m, policies, verdict="PASS", trust_score=0.9)
    assert d.continue_improvement or not d.jira_allowed or m.score >= 0.80


def test_completeness_formula():
    m = CompletenessMetrics.from_events(
        {
            "env_fail_steps": 1,
            "total_steps": 10,
            "tool_incidents": 1,
            "gates_run": 5,
            "llm_fix_rounds": 2,
            "max_rounds": 20,
        }
    )
    assert 0 < m.score < 1


@pytest.mark.integration
def test_verify_group_pass():
    from unittest.mock import patch

    from soc_verify.graphs.orchestrator import run_orchestrator

    import uuid

    tid = f"test-pass-{uuid.uuid4().hex[:8]}"
    with (
        patch("soc_verify.graphs.orchestrator.should_refresh_tag", return_value=False),
        patch("soc_verify.graphs.verify_group.should_refresh_tag", return_value=False),
    ):
        result = run_orchestrator(
            ROOT,
            mode="single_verify",
            project_id="EXAMPLE-SOC",
            stage="simulation",
            group="gpio_ext",
            thread_id=tid,
        )
    vr = result.get("verify_results") or []
    assert vr[-1].get("verdict") == "PASS"
    assert (vr[-1].get("completeness") or 0) > 0


def test_group_context_and_milestone_gate():
    from soc_verify.group_context import load_group_context
    from soc_verify.milestone_gate import check_milestone_gate
    from soc_verify.models import load_yaml

    gdir = EXAMPLE / "verification" / "simulation" / "gpio_ext"
    ctx = load_group_context(gdir)
    assert "CHECK" in ctx["check_md"] or ctx["check_md"]
    assert ctx["milestone_md"]

    state = load_yaml(EXAMPLE / "state.yaml")
    ok, _ = check_milestone_gate(ctx["manifest"], state)
    assert ok


def test_md_only_prompt_excludes_manifest_body():
    from soc_verify.llm_prompt import build_md_only_payload, build_md_only_user_message
    from soc_verify.group_context import load_group_context

    ctx = load_group_context(EXAMPLE / "verification" / "simulation" / "gpio_ext")
    payload = build_md_only_payload(ctx)
    assert "manifest" not in payload
    assert payload["check_md"]
    user = build_md_only_user_message(payload)
    assert "CHECK.md" in user
    assert "git_url" not in user


def test_crystallize_extracts_python():
    from soc_verify.crystallize import apply_crystallize_proposal, extract_python_from_proposal
    import uuid

    text = '## Py\n```python\nprint("x")\n```'
    assert "print" in (extract_python_from_proposal(text) or "")

    run_dir = EXAMPLE / "runs" / f"cryst-test-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "crystallize_proposal.md").write_text(
        '```python\nEXIT_PASS = 0\n```\n',
        encoding="utf-8",
    )
    target = EXAMPLE / "ops" / "simulation" / f"_cryst_{uuid.uuid4().hex[:6]}.py"
    try:
        stage, group = "simulation", target.stem
        result = apply_crystallize_proposal(EXAMPLE, stage, group, run_dir, force=True)
        assert result["applied"] is True
        assert (EXAMPLE / "ops" / "simulation" / f"{group}.py").is_file()
    finally:
        if target.is_file():
            target.unlink()


def test_graph_flow_spec_reproduction_nodes():
    from soc_verify.graph_spec import load_flow_spec, node_spec

    spec = load_flow_spec(ROOT)
    vg = (spec.get("graphs") or {}).get("verify_group", {})
    nodes = vg.get("nodes") or {}
    assert "finalize_reproduction" in nodes
    assert "parity_check" in nodes
    assert "run_codegen" in nodes
    assert "diagnose_env" in nodes
    assert "patch_bridge" in nodes
    edges = vg.get("edges") or {}
    assert "parity_check" in edges.get("evaluate", [])
    assert "run_codegen" in edges.get("parity_check", [])
    fr = node_spec(spec, "verify_group", "finalize_reproduction")
    assert fr.get("llm_trigger") is True
    assert "verification_sequence.yaml" in str(fr.get("writes", []))

    orch = (spec.get("graphs") or {}).get("orchestrator", {})
    assert "finalize_reproduction_sequence" in (orch.get("nodes") or {})
    fs = node_spec(spec, "orchestrator", "finalize_reproduction_sequence")
    assert fs.get("llm_trigger") is True


def test_reproduction_scripts_validation_verif_cpu():
    from soc_verify.reproduction_scripts import validate_gate_step, validate_orchestrator

    project = ROOT / "projects" / "VERIF-CPU-SOC"
    if not project.is_dir():
        pytest.skip("VERIF-CPU-SOC not present")

    coi = validate_gate_step(project, "static", "coi_conn")
    assert coi["ok"] is True
    assert coi["script"].startswith("02_")

    orch = validate_orchestrator(project)
    assert orch["ok"] is True
    assert "run_VERIF-CPU-SOC_verification_sequence.sh" in orch["orchestrator"]


def test_graph_flow_spec_and_session_start():
    from soc_verify.graph_spec import load_flow_spec, node_spec
    from soc_verify.graph_session import start_session

    spec = load_flow_spec(ROOT)
    assert "verify_group" in (spec.get("graphs") or {})
    ns = node_spec(spec, "verify_group", "run_gate")
    assert ns.get("llm_trigger") is True

    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    assert started["session_id"]
    assert "graph_flow_spec.yaml" in started["flow_spec"]


def test_milestone_gate_blocks_future():
    from soc_verify.milestone_gate import check_milestone_gate

    ok, msg = check_milestone_gate({"milestone": "M4"}, {"current_milestone": "M2"})
    assert not ok
    assert "ahead" in msg