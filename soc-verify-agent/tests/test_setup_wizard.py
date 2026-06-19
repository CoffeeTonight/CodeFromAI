from __future__ import annotations

import json
import shutil
from pathlib import Path

from soc_verify.setup_wizard import (
    build_steps,
    load_setup_state,
    run_setup_wizard,
    setup_status,
    save_setup_state,
)


ROOT = Path(__file__).resolve().parents[1]


def _minimal_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    for name in ("registry", "projects/EXAMPLE-SOC"):
        (ws / name).mkdir(parents=True)
    for reg in (
        "setup_wizard_spec.yaml",
        "milestone_plans/index.yaml",
        "milestone_plans/soc-dv-4p-v1.yaml",
        "evaluation_manifest.yaml",
        "paper_readiness_spec.yaml",
    ):
        src = ROOT / "registry" / reg
        if src.is_file():
            dst = ws / "registry" / reg
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
    shutil.copy(ROOT / "config.example.json", ws / "config.example.json")
    state_src = ROOT / "projects" / "EXAMPLE-SOC" / "state.yaml"
    if state_src.is_file():
        shutil.copy(state_src, ws / "projects" / "EXAMPLE-SOC" / "state.yaml")
    return ws


def test_setup_status_empty(tmp_path: Path):
    ws = _minimal_ws(tmp_path)
    st = setup_status(ws)
    assert st["contract"] == "setup_status_v1"
    assert st["progress_percent"] < 100
    assert st["setup_complete"] is False


def test_build_steps_has_llm_and_milestone():
    steps = build_steps()
    ids = [s.id for s in steps]
    assert "llm_provider" in ids
    assert "llm_credentials" in ids
    assert "milestone_plan" in ids
    assert "paper_campaign" in ids
    assert "paper_draft" in ids
    assert "paper_progress" in ids
    assert "orchestrator_schedules" in ids
    assert "node_guide_define" in ids


def test_hub_sections_from_spec(tmp_path: Path):
    from soc_verify.setup_wizard import _hub_sections, load_wizard_spec

    ws = _minimal_ws(tmp_path)
    spec = load_wizard_spec(ws)
    sections = _hub_sections(spec)
    ids = [s["id"] for s in sections]
    assert "paper" in ids
    assert "llm" in ids
    assert "schedules" in ids


def test_non_interactive_setup(tmp_path: Path, capsys):
    ws = _minimal_ws(tmp_path)
    code = run_setup_wizard(ws, non_interactive=True)
    assert code == 1
    out = capsys.readouterr().out
    assert "soc-verify setup" in out


def test_mark_complete_via_state(tmp_path: Path):
    ws = _minimal_ws(tmp_path)
    shutil.copy(ws / "config.example.json", ws / "config.json")
    cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
    cfg["workspace_id"] = "test-ws"
    cfg.setdefault("schedules", {})["default_milestone_plan"] = "soc-dv-4p-v1"
    cfg.setdefault("paper", {})["default_campaign"] = "paper_test"
    cfg.setdefault("llm", {})["mode"] = "openai_compatible"
    cfg["llm"]["openai_compatible"] = {
        "model": "gpt-4o",
        "base_url_default": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_API_BASE",
    }
    from soc_verify.setup_llm import write_secrets_env, secrets_path

    write_secrets_env(secrets_path(ws), {"OPENAI_API_KEY": "sk-test-key-12345"})
    (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    state = load_setup_state(ws)
    state["completed_steps"] = [s.id for s in build_steps() if not s.optional]
    save_setup_state(ws, state)
    st = setup_status(ws)
    assert st["setup_complete"] is True