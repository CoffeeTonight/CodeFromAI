from __future__ import annotations

import json
from pathlib import Path

from soc_verify.experiment import resolve_experiment_tags, write_experiment_run
from soc_verify.paper_factory import (
    find_repo_root,
    format_suggestions_text,
    run_factory,
    suggest_verify_commands,
)
from soc_verify.paper_factory_cli import main as pf_main
from soc_verify.platform_telemetry import ensure_platform_baseline


ROOT = Path(__file__).resolve().parents[1]


def _seed_registry(tmp_root: Path) -> None:
    reg = tmp_root / "registry"
    reg.mkdir(parents=True)
    for name in (
        "evaluation_manifest.yaml",
        "experiment_spec.yaml",
        "paper_readiness_spec.yaml",
        "platform_baseline.yaml",
        "platform_telemetry.yaml",
        "code_change_log.yaml",
    ):
        src = ROOT / "registry" / name
        if src.is_file():
            (reg / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_find_repo_root():
    assert find_repo_root(ROOT) == ROOT.resolve()


def test_suggest_verify_commands(tmp_path: Path):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")
    (root / "projects" / "EXAMPLE-SOC").mkdir(parents=True)

    suggestions = suggest_verify_commands(root, "camp1")
    assert len(suggestions) >= 2
    text = format_suggestions_text(suggestions, campaign="camp1", overall_percent=10.0, verdict="bootstrap")
    assert "soc-verify" in text
    assert "control" in text


def test_run_factory_writes_artifacts(tmp_path: Path, capsys):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")
    campaign = "pf_run"
    run_dir = root / "projects" / "EXAMPLE-SOC" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    write_experiment_run(
        run_dir,
        resolve_experiment_tags(root, campaign=campaign, condition="treatment_full"),
    )
    (run_dir / "improvement_snapshot.json").write_text(
        json.dumps(
            {
                "stage": "simulation",
                "group": "gpio_ext",
                "verdict": "PASS",
                "improvement_index": 0.9,
                "trust_score": 0.85,
            }
        ),
        encoding="utf-8",
    )

    report = run_factory(root, campaign, write=True, export=False, max_suggestions=2)
    assert report.overall_percent > 0
    suggest_path = root / "exports" / campaign / "suggested_commands.sh"
    assert suggest_path.is_file()
    assert "soc-verify" in suggest_path.read_text(encoding="utf-8")


def test_paper_factory_cli_assess_json(tmp_path: Path, capsys):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")

    code = pf_main(["--root", str(root), "assess", "--campaign", "cli_test", "--json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["contract"] == "paper_readiness_v1"
    assert code == 1