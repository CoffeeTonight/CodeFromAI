#!/usr/bin/env python3
"""Static COI connectivity — connect trace on hierarchy-validated checks only."""

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
    append_gate_log,
    checks_path,
    judge_checks,
    load_checks_spec,
    resolve_scan_inst,
    run_scan_inst,
    scan_inst_batch_payload,
    parse_connect_tsv,
    scan_log_hits,
    wait_for_validated_checks,
)

GATE = "coi_conn"
GEN_MARKER = "include/chip_top_example_gen.vh"


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
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[str(exc)], log_path=log_path)
        return EXIT_FAIL

    if not (root / GEN_MARKER).is_file():
        msg = f"c-compile/gen prerequisite missing: {GEN_MARKER}"
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[msg], log_path=log_path)
        return EXIT_FAIL

    try:
        checks_path_resolved = checks_path(project_dir, run_dir)
        spec = load_checks_spec(checks_path_resolved)
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
    append_gate_log(log_path, "conn consumer started — waiting for hierarchy validated checks")

    try:
        hierarchy = wait_for_validated_checks(run_dir, log_path=log_path)
    except TimeoutError as exc:
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[str(exc)], log_path=log_path)
        return EXIT_FAIL

    hierarchy_status = str(hierarchy.get("status") or "")
    validated_checks = list(hierarchy.get("validated_checks") or [])
    failed_hierarchy = list(hierarchy.get("failed_checks") or [])

    if hierarchy_status == "failed":
        evidence = ["coi_hierarchy producer failed before connect trace"]
        for item in failed_hierarchy[:4]:
            cid = str(item.get("id") or "?")
            errs = item.get("hierarchy_errors") or []
            evidence.append(f"{cid}: {' | '.join(errs)[:120]}")
        _write_verdict(
            run_dir,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=evidence,
            log_path=log_path,
            checks_path=checks_path_resolved,
            hierarchy_failed=len(failed_hierarchy),
        )
        return EXIT_FAIL

    if not validated_checks:
        evidence = [
            "no hierarchy-validated checks — connect trace skipped",
            f"hierarchy status={hierarchy_status!r} failed={len(failed_hierarchy)}",
        ]
        for item in failed_hierarchy[:6]:
            cid = str(item.get("id") or "?")
            errs = item.get("hierarchy_errors") or []
            evidence.append(f"{cid}: {' | '.join(errs)[:120]}")
        _write_verdict(
            run_dir,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=evidence,
            log_path=log_path,
            checks_path=checks_path_resolved,
            hierarchy_failed=len(failed_hierarchy),
        )
        return EXIT_FAIL

    append_gate_log(
        log_path,
        f"connect trace on {len(validated_checks)} validated check(s) "
        f"(skipped {len(failed_hierarchy)} hierarchy-failed)",
    )

    batch_path = run_dir / "coi_conn_scan_batch.json"
    batch_path.write_text(
        json.dumps(scan_inst_batch_payload(spec, checks=validated_checks), indent=2),
        encoding="utf-8",
    )

    try:
        scan_bin = resolve_scan_inst()
    except FileNotFoundError as exc:
        _write_verdict(run_dir, status="FAIL", exit_code=EXIT_FAIL, evidence=[str(exc)], log_path=log_path)
        return EXIT_FAIL

    tsv_path = run_dir / f"{GATE}.tsv"
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
    checks_ok, check_hits = judge_checks({"checks": validated_checks}, tsv_rows)

    evidence: list[str] = []
    if log_hits:
        evidence.extend(log_hits[:8])
    if failed_hierarchy:
        evidence.append(f"hierarchy failed {len(failed_hierarchy)} check(s) — connect skipped for those")
        for item in failed_hierarchy[:4]:
            cid = str(item.get("id") or "?")
            errs = item.get("hierarchy_errors") or []
            evidence.append(f"{cid}: {' | '.join(errs)[:120]}")
    if not checks_ok:
        evidence.extend(check_hits[:8])

    if log_hits or not checks_ok or failed_hierarchy:
        _write_verdict(
            run_dir,
            status="FAIL",
            exit_code=EXIT_FAIL,
            evidence=evidence or ["coi_conn gate failed"],
            log_path=log_path,
            tsv_path=tsv_path,
            checks_path=checks_path_resolved,
            tsv_rows=tsv_rows,
            hierarchy_failed=len(failed_hierarchy),
            connect_ran=len(validated_checks),
        )
        return EXIT_FAIL

    evidence = [
        f"scan_inst OK — {len(validated_checks)} validated check(s) matched expected_connected",
        f"checks: {checks_path_resolved.name}",
    ]
    _write_verdict(
        run_dir,
        status="PASS",
        exit_code=EXIT_PASS,
        evidence=evidence,
        log_path=log_path,
        tsv_path=tsv_path,
        checks_path=checks_path_resolved,
        tsv_rows=tsv_rows,
        hierarchy_failed=0,
        connect_ran=len(validated_checks),
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
    hierarchy_failed: int | None = None,
    connect_ran: int | None = None,
) -> None:
    verdict: dict = {
        "gate": GATE,
        "status": status,
        "exit_code": exit_code,
        "evidence": evidence,
        "artifacts": {
            "log": str(log_path),
        },
        "trust": {"script": "coi_conn.py", "version": "0.3.0"},
    }
    if tsv_path:
        verdict["artifacts"]["tsv"] = str(tsv_path)
    if checks_path:
        verdict["artifacts"]["checks"] = str(checks_path)
    verdict["artifacts"]["hierarchy_validated"] = str(run_dir / "coi_hierarchy_validated.json")
    if tsv_rows is not None:
        verdict["connectivity"] = {
            cid: {
                "connected": row.get("connected"),
                "errors": row.get("errors", ""),
            }
            for cid, row in tsv_rows.items()
        }
    if hierarchy_failed is not None or connect_ran is not None:
        verdict["conn_pipeline"] = {
            "hierarchy_failed": hierarchy_failed or 0,
            "connect_ran": connect_ran or 0,
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