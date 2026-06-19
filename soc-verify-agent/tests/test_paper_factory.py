from __future__ import annotations

import json
from pathlib import Path

from soc_verify.experiment import (
    evaluation_progress,
    find_runs_for_campaign,
    resolve_experiment_tags,
    write_experiment_run,
)
from soc_verify.paper_export import export_paper
from soc_verify.repro_env import capture_env_pin


ROOT = Path(__file__).resolve().parents[1]


def test_resolve_experiment_tags_default_campaign():
    tags = resolve_experiment_tags(ROOT, campaign="test_camp", condition="control", hypothesis="H1")
    assert tags["campaign"] == "test_camp"
    assert tags["condition"] == "control"
    assert tags["hypothesis"] == "H1"


def test_export_paper_campaign(tmp_path: Path):
    root = tmp_path / "ws"
    (root / "registry").mkdir(parents=True)
    for name in ("evaluation_manifest.yaml", "experiment_spec.yaml"):
        (ROOT / "registry" / name).read_text(encoding="utf-8")
        (root / "registry" / name).write_text(
            (ROOT / "registry" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    project = root / "projects" / "P1"
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    write_experiment_run(
        run_dir,
        resolve_experiment_tags(root, campaign="exp1", condition="treatment_full"),
    )
    (run_dir / "improvement_snapshot.json").write_text(
        json.dumps(
            {
                "stage": "sim",
                "group": "g",
                "verdict": "PASS",
                "improvement_index": 0.9,
                "trust_score": 0.85,
            }
        ),
        encoding="utf-8",
    )

    out = root / "exports"
    result = export_paper(root, "exp1", out)
    assert result["run_count"] == 1
    assert (out / "runs.csv").is_file()
    assert (out / "methods.md").is_file()
    assert (out / "methods.json").is_file()


def test_find_runs_for_campaign(tmp_path: Path):
    root = tmp_path / "ws"
    run_dir = root / "projects" / "P" / "runs" / "rx"
    run_dir.mkdir(parents=True)
    write_experiment_run(run_dir, {"campaign": "c1", "condition": "control"})
    found = find_runs_for_campaign(root, "c1")
    assert len(found) == 1


def test_env_pin_has_git_or_none(tmp_path: Path):
    pin = capture_env_pin(tmp_path)
    assert "config_json_sha256" in pin
    assert "pip_freeze_sha256" in pin


def test_evaluation_progress_reads_manifest():
    prog = evaluation_progress(ROOT, "paper_eval_2026")
    assert "gates_total" in prog