#!/usr/bin/env python3
"""Sanity rtl_sim — VerifCPU full_campaign sim + VCD post-check (c-compile fw only)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _verifcpu import (  # noqa: E402
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_TOOL_ERROR,
    fw_artifact_manifest,
    fw_artifacts_unchanged,
    init_log,
    judge_log,
    missing_fw_artifacts,
    rtl_root,
    run_cmd,
    write_verdict,
)

GATE = "rtl_sim"
VVP_ARTIFACT = "sim_build/tb_full_campaign.vvp"
VCD_ARTIFACT = "sim_build/tb_full_campaign.vcd"
LOG_FULL = "logs/full_campaign"


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

    if not (root / VVP_ARTIFACT).is_file():
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=[f"c-compile prerequisite missing: {VVP_ARTIFACT}"],
            artifacts={"log": str(log_path)},
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
    (root / LOG_FULL).mkdir(parents=True, exist_ok=True)

    # Sim-only: do NOT call ./example.sh sim (make full_campaign rebuilds C fw).
    run_cmd(["vvp", VVP_ARTIFACT], cwd=root, log_path=log_path)
    run_cmd(
        ["python3", "tools/verify_vcd.py", VCD_ARTIFACT],
        cwd=root,
        log_path=log_path,
    )

    fw_after = fw_artifact_manifest(root)
    fw_hits = fw_artifacts_unchanged(fw_before, fw_after)

    scan = judge_log(log_path, gate=GATE)
    if fw_hits:
        scan = type(scan)(ok=False, hits=scan.hits + fw_hits)

    vcd_path = root / VCD_ARTIFACT

    if not scan.ok:
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=scan.evidence,
            artifacts={
                "log": str(log_path),
                "rtl_root": str(root),
                "firmware_before": fw_before,
                "firmware_after": fw_after,
            },
            log_scan=scan,
        )
        return EXIT_FAIL

    if not vcd_path.is_file():
        scan = type(scan)(ok=False, hits=scan.hits + [f"missing artifact: {VCD_ARTIFACT}"])
        write_verdict(
            run_dir,
            GATE,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=scan.evidence,
            artifacts={"log": str(log_path), "rtl_root": str(root)},
            log_scan=scan,
        )
        return EXIT_FAIL

    evidence = scan.evidence + [
        f"sim used c-compile fw ({len(fw_before)} artifacts, unchanged)",
        f"artifact OK → {vcd_path}",
    ]
    write_verdict(
        run_dir,
        GATE,
        status="PASS",
        exit_code=EXIT_PASS,
        evidence=evidence,
        artifacts={
            "log": str(log_path),
            "vcd": str(vcd_path),
            "rtl_root": str(root),
            "firmware": fw_before,
        },
        log_scan=scan,
    )
    return EXIT_PASS


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        raise SystemExit(EXIT_TOOL_ERROR)