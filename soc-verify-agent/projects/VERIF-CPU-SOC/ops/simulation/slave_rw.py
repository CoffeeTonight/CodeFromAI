#!/usr/bin/env python3
"""Simulation slave_rw — VerifCPU single / burst / cpu_sync R/W (slave_rw.md)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sanity"))
from _verifcpu import (  # noqa: E402
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_TOOL_ERROR,
    _log_stamp,
    fw_artifact_manifest,
    fw_artifacts_unchanged,
    init_log,
    missing_fw_artifacts,
    rtl_root,
    run_cmd,
    write_verdict,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from intake_resolve import load_slave_rw_scenarios, project_tag  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _slave_rw import GATE, PREREQ_MARKERS, SOC_DUT_VVP, judge_slave_rw_log  # noqa: E402

BUS_ALL_VVP = "sim_build/tb_soc_bus_all.vvp"
FULL_VVP = "sim_build/tb_full_campaign.vvp"
BUS_ALL_VCD = "sim_build/tb_soc_bus_all.vcd"


def _tier_banner(tier: str) -> str:
    return f"\n{'=' * 72}\n# {_log_stamp()}\n# tier={tier}\n"


def _append_log(log_path: Path, text: str) -> None:
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def _missing_prereqs(root: Path) -> list[str]:
    return [rel for rel in PREREQ_MARKERS if not (root / rel).is_file()]


def _run_integration_smoke(root: Path, scenarios: dict[str, Any], log_path: Path) -> None:
    smoke = scenarios.get("integration_smoke") or {}
    if not smoke.get("run_in_s10_gate"):
        return
    cmd = str(smoke.get("command") or "").strip()
    if not cmd:
        return
    _append_log(log_path, _tier_banner("integration_smoke"))
    cmd = cmd.replace("{RTL_ROOT}", str(root))
    run_cmd(["bash", "-lc", f"export RTL_ROOT={root}; {cmd}"], cwd=root, log_path=log_path)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    project_dir = Path(args.project)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / f"{GATE}.log"

    try:
        root = rtl_root(project_dir)
    except FileNotFoundError as exc:
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=[str(exc)],
            artifacts={"log": str(log_path)},
        )
        return EXIT_FAIL

    tag = project_tag(project_dir)
    scenarios = load_slave_rw_scenarios(project_dir, tag=tag)

    missing = _missing_prereqs(root)
    if missing:
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=[f"sanity/c-compile prerequisite missing: {', '.join(missing)}"],
            artifacts={"log": str(log_path), "rtl_root": str(root)},
        )
        return EXIT_FAIL

    missing_fw = missing_fw_artifacts(root)
    if missing_fw:
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=[f"c-compile firmware missing: {', '.join(missing_fw)}"],
            artifacts={"log": str(log_path), "rtl_root": str(root)},
        )
        return EXIT_FAIL

    fw_before = fw_artifact_manifest(root)
    init_log(log_path, gate=GATE, rtl_root_path=root)
    _append_log(
        log_path,
        f"# scenarios={json.dumps({'source': scenarios.get('source'), 'intake_tag': scenarios.get('intake_tag')})}\n",
    )

    _run_integration_smoke(root, scenarios, log_path)

    _append_log(log_path, _tier_banner("compile"))
    run_cmd(["make", SOC_DUT_VVP], cwd=root, log_path=log_path)
    run_cmd(["make", BUS_ALL_VVP], cwd=root, log_path=log_path)

    _append_log(log_path, _tier_banner("sim_single"))
    run_cmd(["vvp", SOC_DUT_VVP], cwd=root, log_path=log_path)

    _append_log(log_path, _tier_banner("sim_burst"))
    run_cmd(["vvp", BUS_ALL_VVP], cwd=root, log_path=log_path)
    run_cmd(
        ["python3", "tools/verify_amba_bus_vcd.py", BUS_ALL_VCD],
        cwd=root,
        log_path=log_path,
    )

    _append_log(log_path, _tier_banner("sim_cpu_sync"))
    run_cmd(["vvp", FULL_VVP], cwd=root, log_path=log_path)

    fw_after = fw_artifact_manifest(root)
    fw_hits = fw_artifacts_unchanged(fw_before, fw_after)

    scan, tiers = judge_slave_rw_log(log_path, scenarios=scenarios)
    if fw_hits:
        scan = type(scan)(ok=False, hits=scan.hits + fw_hits)

    tier_summary = {t.tier: {"ok": t.ok, "hits": t.hits[:6]} for t in tiers}
    artifacts: dict[str, Any] = {
        "log": str(log_path),
        "rtl_root": str(root),
        "firmware_before": fw_before,
        "firmware_after": fw_after,
        "tiers": tier_summary,
        "scenarios_source": scenarios.get("source"),
    }

    if not scan.ok:
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=scan.evidence,
            artifacts=artifacts,
            log_scan=scan,
        )
        return EXIT_FAIL

    evidence = scan.evidence + [
        "all tiers PASS: sim_single, sim_burst, sim_cpu_sync",
        f"fw unchanged ({len(fw_before)} c-compile artifacts)",
    ]
    write_verdict(
        run_dir,
        GATE,
        status="PASS",
        exit_code=EXIT_PASS,
        evidence=evidence,
        artifacts=artifacts,
        log_scan=scan,
    )
    return EXIT_PASS


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        raise SystemExit(EXIT_TOOL_ERROR)