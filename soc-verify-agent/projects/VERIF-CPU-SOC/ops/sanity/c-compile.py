#!/usr/bin/env python3
"""Sanity c-compile — VerifCPU gen + iverilog elaborate (no sim)."""

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
    init_log,
    judge_log,
    missing_fw_artifacts,
    rtl_root,
    run_cmd,
    write_verdict,
)

GATE = "c-compile"
VVP_ARTIFACT = "sim_build/tb_full_campaign.vvp"


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

    init_log(log_path, gate=GATE, rtl_root_path=root)

    run_cmd(["./example.sh", "gen"], cwd=root, log_path=log_path)
    run_cmd(["make", VVP_ARTIFACT], cwd=root, log_path=log_path)

    scan = judge_log(log_path, gate=GATE)
    vvp_path = root / VVP_ARTIFACT

    if not scan.ok:
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

    if not vvp_path.is_file():
        scan = type(scan)(ok=False, hits=scan.hits + [f"missing artifact: {VVP_ARTIFACT}"])
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

    missing_fw = missing_fw_artifacts(root)
    if missing_fw:
        scan = type(scan)(ok=False, hits=scan.hits + [f"missing firmware: {m}" for m in missing_fw])
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

    fw_manifest = fw_artifact_manifest(root)
    evidence = scan.evidence + [f"artifact OK → {vvp_path}", f"c-fw deliverables: {len(fw_manifest)}"]
    write_verdict(
        run_dir,
        GATE,
        status="PASS",
        exit_code=EXIT_PASS,
        evidence=evidence,
        artifacts={
            "log": str(log_path),
            "vvp": str(vvp_path),
            "rtl_root": str(root),
            "firmware": fw_manifest,
        },
        log_scan=scan,
    )
    return EXIT_PASS


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        raise SystemExit(EXIT_TOOL_ERROR)