#!/usr/bin/env python3
"""Static COI connectivity — scan_inst batch vs expected_connected (coi_conn.md)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sanity"))
from _verifcpu import EXIT_FAIL, EXIT_PASS, EXIT_TOOL_ERROR, rtl_root  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coi_conn import (  # noqa: E402
    EXIT_INFO_GAP,
    judge_checks,
    load_checks_spec,
    resolve_scan_inst,
    run_scan_inst,
    scan_inst_batch_payload,
    parse_connect_tsv,
    scan_log_hits,
)

GATE = "coi_conn"
GEN_MARKER = "include/chip_top_example_gen.vh"
DEFAULT_CHECKS = "verification/static/coi_conn/coi_conn_checks.json"


def _checks_path(project_dir: Path, run_dir: Path) -> Path:
    for candidate in (
        run_dir / "coi_conn_checks.json",
        project_dir / DEFAULT_CHECKS,
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("coi_conn_checks.json not found (run_dir or project default)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    project_dir = Path(args.project)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / f"{GATE}.log"
    tsv_path = run_dir / f"{GATE}.tsv"

    try:
        root = rtl_root(project_dir)
    except FileNotFoundError as exc:
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[str(exc)], log_path=log_path)
        return EXIT_FAIL

    if not (root / GEN_MARKER).is_file():
        msg = f"c-compile/gen prerequisite missing: {GEN_MARKER}"
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[msg], log_path=log_path)
        return EXIT_FAIL

    try:
        checks_path = _checks_path(project_dir, run_dir)
        spec = load_checks_spec(checks_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        _write_verdict(run_dir, status="INFO_GAP", exit_code=EXIT_INFO_GAP, evidence=[str(exc)], log_path=log_path)
        return EXIT_INFO_GAP

    filelist_rel = str(spec.get("filelist") or "filelists/eda/test/chip_top_example/manifest.list")
    filelist = root / filelist_rel
    if not filelist.is_file():
        _write_verdict(
            run_dir,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=[f"filelist not found: {filelist}"],
            log_path=log_path,
        )
        return EXIT_FAIL

    top = str(spec.get("top") or "chip_top_example")
    batch_path = run_dir / "coi_conn_scan_batch.json"
    batch_path.write_text(
        json.dumps(scan_inst_batch_payload(spec), indent=2),
        encoding="utf-8",
    )

    try:
        scan_bin = resolve_scan_inst()
    except FileNotFoundError as exc:
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[str(exc)], log_path=log_path)
        return EXIT_FAIL

    proc = run_scan_inst(
        scan_bin=scan_bin,
        rtl_root=root,
        filelist=filelist,
        batch_json=batch_path,
        tsv_out=tsv_path,
        log_path=log_path,
        top=top,
    )

    log_hits = scan_log_hits(log_path)
    if proc.returncode != 0:
        log_hits.append(f"scan-inst exit {proc.returncode}")

    if not tsv_path.is_file():
        log_hits.append(f"missing TSV: {tsv_path}")

    tsv_rows = parse_connect_tsv(tsv_path) if tsv_path.is_file() else {}
    checks_ok, check_hits = judge_checks(spec, tsv_rows)

    evidence: list[str] = []
    if log_hits:
        evidence.extend(log_hits[:8])
    if not checks_ok:
        evidence.extend(check_hits[:8])

    if log_hits or not checks_ok:
        _write_verdict(
            run_dir,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=evidence or ["coi_conn gate failed"],
            log_path=log_path,
            tsv_path=tsv_path,
            checks_path=checks_path,
            tsv_rows=tsv_rows,
        )
        return EXIT_FAIL

    evidence = [
        f"scan_inst OK — {len(spec.get('checks', []))} checks matched expected_connected",
        f"checks: {checks_path.name}",
    ]
    _write_verdict(
        run_dir,
        status="PASS",
        exit_code=EXIT_PASS,
        evidence=evidence,
        log_path=log_path,
        tsv_path=tsv_path,
        checks_path=checks_path,
        tsv_rows=tsv_rows,
    )
    return EXIT_PASS


def _write_verdict(
    run_dir: Path,
    *,
    status: str,
    exit_code: int,
    evidence: list[str],
    log_path: Path,
    tsv_path: Path | None = None,
    checks_path: Path | None = None,
    tsv_rows: dict | None = None,
) -> None:
    verdict: dict = {
        "gate": GATE,
        "status": status,
        "exit_code": exit_code,
        "evidence": evidence,
        "artifacts": {
            "log": str(log_path),
        },
        "trust": {"script": "coi_conn.py", "version": "0.2.0"},
    }
    if tsv_path:
        verdict["artifacts"]["tsv"] = str(tsv_path)
    if checks_path:
        verdict["artifacts"]["checks"] = str(checks_path)
    if tsv_rows is not None:
        verdict["connectivity"] = {
            cid: {
                "connected": row.get("connected"),
                "errors": row.get("errors", ""),
            }
            for cid, row in tsv_rows.items()
        }
    (run_dir / f"verdict_{GATE}.json").write_text(
        json.dumps(verdict, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        raise SystemExit(EXIT_TOOL_ERROR)