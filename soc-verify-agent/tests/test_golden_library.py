from __future__ import annotations

import json
from pathlib import Path

from soc_verify.golden_library import (
    capture_from_verdict,
    golden_allows_promote,
    run_golden_suite,
    write_golden_report,
)
from soc_verify.registry_writer import apply_promotion

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_capture_and_replay_golden(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "trust" / "golden" / "v1").mkdir(parents=True)
    (project / "cache.yaml").write_text("tag:\n  value: v1\n", encoding="utf-8")

    script = tmp_path / "fake_ops.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, json, sys\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--project')\n"
        "p.add_argument('--case', default=None)\n"
        "a = p.parse_args()\n"
        "print(json.dumps({'status': 'PASS'}))\n",
        encoding="utf-8",
    )

    verdict = {"status": "PASS", "gate": "g1", "evidence": ["ok"], "exit_code": 0}
    cap = capture_from_verdict(
        project, stage="sim", group="g1", tag="v1", verdict=verdict, run_id="r1"
    )
    assert cap["captured"] is True

    report = run_golden_suite(project, script, tag="v1")
    assert report["ok"] is True
    assert report["total"] == 1


def test_golden_mismatch_blocks_promote(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    gdir = project / "trust" / "golden" / "t1"
    gdir.mkdir(parents=True)
    (project / "trust" / "registry.yaml").write_text("scripts: {}\n", encoding="utf-8")
    (project / "cache.yaml").write_text("tag:\n  value: t1\n", encoding="utf-8")

    case = gdir / "sim__g__abc.json"
    case.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")

    script = tmp_path / "bad_ops.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, json\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--project')\n"
        "p.add_argument('--case', default=None)\n"
        "a = p.parse_args()\n"
        "print(json.dumps({'status': 'FAIL'}))\n",
        encoding="utf-8",
    )

    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "promote_decision.md").write_text("decision: approve\n", encoding="utf-8")
    (run_dir / "parity_report.json").write_text(
        json.dumps({"ok": True, "contract": "parity_eval_v1"}),
        encoding="utf-8",
    )

    report = run_golden_suite(project, script, tag="t1")
    write_golden_report(run_dir, report)
    assert golden_allows_promote(run_dir) == (False, "golden_fail")

    outcome = apply_promotion(
        project,
        "g.py",
        trust_score=0.9,
        run_dir=run_dir,
    )
    assert outcome["promoted"] is False
    assert outcome["reason"] == "golden_fail"