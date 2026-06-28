"""COI hierarchy → conn producer-consumer pipeline helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COI_OPS = ROOT / "projects" / "VERIF-CPU-SOC" / "ops" / "static"
sys_path_insert = str(COI_OPS)
import sys

if sys_path_insert not in sys.path:
    sys.path.insert(0, sys_path_insert)

from _coi_conn import (  # noqa: E402
    VALIDATED_ARTIFACT,
    build_hierwalk_connect_cmd,
    endpoint_specs_from_checks,
    judge_checks,
    parse_connect_tsv,
    path_walk_connect_artifact_paths,
    read_validated_artifact,
    hierwalk_batch_payload,
    wait_for_validated_checks,
    write_validated_artifact,
)


def test_append_gate_log_survives_hierwalk_block(tmp_path: Path):
    from _coi_conn import append_gate_log

    log = tmp_path / "coi_conn.log"
    append_gate_log(log, "conn consumer started")
    block = "\n--- hier-walk connect trace ---\n# started=test\nexit=0\n"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(block)
    body = log.read_text(encoding="utf-8")
    assert "conn consumer started" in body
    assert "hier-walk connect trace" in body


def test_endpoint_specs_dedupes_a_b():
    checks = [
        {"id": "x", "a": "top.u_a.sig", "b": "top.u_b.sig", "expected_connected": True},
        {"id": "y", "a": "top.u_a.sig", "b": "top.u_c.sig", "expected_connected": False},
    ]
    specs = endpoint_specs_from_checks(checks)
    assert specs == ["top.u_a.sig", "top.u_b.sig", "top.u_c.sig"]


def test_hierwalk_batch_payload_subset():
    spec = {
        "top": "chip_top",
        "connect_trace": True,
        "checks": [
            {"id": "a", "a": "top.u1", "b": "top.u2", "expected_connected": True},
            {"id": "b", "a": "top.u3", "b": "top.u4", "expected_connected": False},
        ],
    }
    subset = [spec["checks"][0]]
    payload = hierwalk_batch_payload(spec, checks=subset)
    assert payload["top"] == "chip_top"
    assert payload["connect_log"] is True
    assert len(payload["checks"]) == 1
    assert payload["checks"][0]["id"] == "a"


def test_wait_blocks_until_validated(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log_path = run_dir / "coi_conn.log"

    def _producer() -> None:
        time.sleep(0.3)
        write_validated_artifact(
            run_dir,
            {
                "status": "running",
                "validated_checks": [],
                "failed_checks": [],
            },
        )
        time.sleep(0.3)
        write_validated_artifact(
            run_dir,
            {
                "status": "complete",
                "validated_checks": [{"id": "ok", "a": "t.a", "b": "t.b", "expected_connected": True}],
                "failed_checks": [],
            },
        )

    import threading

    threading.Thread(target=_producer, daemon=True).start()
    t0 = time.monotonic()
    body = wait_for_validated_checks(
        run_dir,
        log_path=log_path,
        timeout_sec=5.0,
        poll_sec=0.05,
    )
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.25
    assert len(body.get("validated_checks") or []) == 1
    assert read_validated_artifact(run_dir / VALIDATED_ARTIFACT) is not None


def test_build_hierwalk_connect_cmd_uses_path_walk_mode(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    fl = rtl / "fl.f"
    batch = rtl / "batch.json"
    out = rtl / "coi_conn.tsv"
    cmd = build_hierwalk_connect_cmd(
        scan_bin="/usr/bin/hier-walk",
        filelist=fl,
        batch_json=batch,
        tsv_out=out,
        rtl_root=rtl,
        top="chip_top_example",
    )
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "path-walk"
    assert "--no-cache" in cmd
    assert "--check-connect-batch" in cmd


def test_parse_connect_tsv_skips_hierwalk_comment_header(tmp_path: Path):
    tsv = tmp_path / "coi_conn.tsv"
    tsv.write_text(
        "# connect results\n"
        "check_id\tendpoint_a\tendpoint_b\tconnected\n"
        "sfr_clk_to_sram_clk\ta\tb\tTrue\n",
        encoding="utf-8",
    )
    rows = parse_connect_tsv(tsv)
    assert list(rows) == ["sfr_clk_to_sram_clk"]
    ok, hits = judge_checks(
        {"checks": [{"id": "sfr_clk_to_sram_clk", "expected_connected": True}]},
        rows,
    )
    assert ok is True
    assert hits == []


def test_path_walk_connect_artifact_paths_under_db_top(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    tsv_out = rtl / "coi_conn.tsv"
    text_path, logical_path = path_walk_connect_artifact_paths(
        rtl, "chip_top_example", tsv_out=tsv_out
    )
    assert text_path == rtl / ".db_chip_top_example" / "coi_conn.text.tsv"
    assert logical_path == rtl / ".db_chip_top_example" / "coi_conn.tsv"


def test_validate_intake_tier_rejects_extra_log_markers():
    example = ROOT / "projects" / "VERIF-CPU-SOC" / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    vcpu_project = ROOT / "projects" / "VERIF-CPU-SOC"
    if str(vcpu_project) not in sys.path:
        sys.path.insert(0, str(vcpu_project))
    from soc_verify.models import load_yaml
    from ops.intake_resolve import validate_intake_tier_consistency

    intake = load_yaml(example) or {}
    intake["chip"]["integration_tier"] = "paste"
    intake.setdefault("simulation", {}).setdefault("pass", {})["log_markers"] = [
        "soc_cpu_bus_paste: PASS",
        "Checklist: 4 passed / 0 failed",
        "stale chip_top_example marker",
    ]
    errors = validate_intake_tier_consistency(intake)
    assert any("unexpected" in err for err in errors)


def test_generate_reports_resolves_stale_index_when_verdicts_exist(tmp_path: Path):
    project = tmp_path / "proj"
    runs = project / "runs"
    stale = "coi-conn-test"
    latest = "reproduce-main-20260102-020202"
    for run_id in (stale, latest):
        run_dir = runs / run_id
        run_dir.mkdir(parents=True)
        for name in ("verdict_coi_conn.json", "verdict_slave_rw.json"):
            (run_dir / name).write_text('{"status":"PASS","gate":"x"}', encoding="utf-8")
    reports_dir = project / "reports" / "by_tag" / "main"
    reports_dir.mkdir(parents=True)
    (project / "reports" / "index.yaml").write_text(
        "\n".join(
            [
                "project_id: VERIF-CPU-SOC",
                "tag: main",
                "gates:",
                "  - stage: static",
                "    group: coi_conn",
                "    title: coi",
                "    run_id: coi-conn-test",
                "    verdict: runs/coi-conn-test/verdict_coi_conn.json",
                "    report: reports/by_tag/main/static_coi_conn.md",
                "  - stage: simulation",
                "    group: slave_rw",
                "    title: slave",
                "    run_id: exit-scan-test2",
                "    verdict: runs/exit-scan-test2/verdict_slave_rw.json",
                "    report: reports/by_tag/main/simulation_slave_rw.md",
            ]
        ),
        encoding="utf-8",
    )
    vcpu_project = ROOT / "projects" / "VERIF-CPU-SOC"
    if str(vcpu_project) not in sys.path:
        sys.path.insert(0, str(vcpu_project))
    from ops.report.generate_reports import _load_yaml, generate

    generate(project, run_id=None)
    index = _load_yaml(project / "reports" / "index.yaml")
    assert index["gates"][0]["run_id"] == latest
    assert index["gates"][1]["run_id"] == latest


def test_generate_reports_falls_back_when_explicit_run_id_incomplete(tmp_path: Path):
    project = tmp_path / "proj"
    runs = project / "runs"
    latest = "reproduce-main-20260102-020202"
    latest_dir = runs / latest
    latest_dir.mkdir(parents=True)
    for name in ("verdict_coi_conn.json", "verdict_slave_rw.json"):
        (latest_dir / name).write_text('{"status":"PASS","gate":"x"}', encoding="utf-8")
    reports_dir = project / "reports" / "by_tag" / "main"
    reports_dir.mkdir(parents=True)
    (project / "reports" / "index.yaml").write_text(
        "\n".join(
            [
                "project_id: VERIF-CPU-SOC",
                "tag: main",
                "gates:",
                "  - stage: static",
                "    group: coi_conn",
                "    title: coi",
                "    run_id: coi-conn-test",
                "    verdict: runs/coi-conn-test/verdict_coi_conn.json",
                "    report: reports/by_tag/main/static_coi_conn.md",
            ]
        ),
        encoding="utf-8",
    )
    vcpu_project = ROOT / "projects" / "VERIF-CPU-SOC"
    if str(vcpu_project) not in sys.path:
        sys.path.insert(0, str(vcpu_project))
    from ops.report.generate_reports import _load_yaml, generate

    generate(project, run_id="coi-conn-test")
    index = _load_yaml(project / "reports" / "index.yaml")
    assert index["gates"][0]["run_id"] == latest


def test_generate_reports_auto_resolves_latest_reproduce_run(tmp_path: Path):
    project = tmp_path / "proj"
    runs = project / "runs"
    latest = "reproduce-main-20260102-020202"
    latest_dir = runs / latest
    latest_dir.mkdir(parents=True)
    for name in ("verdict_coi_conn.json", "verdict_slave_rw.json"):
        (latest_dir / name).write_text('{"status":"PASS","gate":"x"}', encoding="utf-8")
    reports_dir = project / "reports" / "by_tag" / "main"
    reports_dir.mkdir(parents=True)
    (project / "reports" / "index.yaml").write_text(
        "\n".join(
            [
                "project_id: VERIF-CPU-SOC",
                "tag: main",
                "gates:",
                "  - stage: static",
                "    group: coi_conn",
                "    title: coi",
                "    run_id: coi-conn-test",
                "    verdict: runs/coi-conn-test/verdict_coi_conn.json",
                "    report: reports/by_tag/main/static_coi_conn.md",
                "  - stage: simulation",
                "    group: slave_rw",
                "    title: slave",
                "    run_id: exit-scan-test2",
                "    verdict: runs/exit-scan-test2/verdict_slave_rw.json",
                "    report: reports/by_tag/main/simulation_slave_rw.md",
            ]
        ),
        encoding="utf-8",
    )
    vcpu_project = ROOT / "projects" / "VERIF-CPU-SOC"
    if str(vcpu_project) not in sys.path:
        sys.path.insert(0, str(vcpu_project))
    from ops.report.generate_reports import _load_yaml, generate

    generate(project, run_id=None)
    index = _load_yaml(project / "reports" / "index.yaml")
    assert index["gates"][0]["run_id"] == latest
    assert index["gates"][1]["run_id"] == latest
    assert (project / "reports" / "by_tag" / "main" / "SUMMARY.md").is_file()


def test_wait_returns_complete_with_zero_validated(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_validated_artifact(
        run_dir,
        {
            "status": "complete",
            "validated_checks": [],
            "failed_checks": [{"id": "bad", "hierarchy_errors": ["a: miss"]}],
        },
    )
    body = wait_for_validated_checks(
        run_dir,
        log_path=run_dir / "coi_conn.log",
        timeout_sec=2.0,
        poll_sec=0.05,
    )
    assert body["status"] == "complete"
    assert body["validated_checks"] == []