#!/usr/bin/env python3
"""Static COI hierarchy — validate endpoint paths before connect tracing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sanity"))
from _verifcpu import EXIT_FAIL, EXIT_PASS, EXIT_TOOL_ERROR, rtl_root  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coi_conn import (  # noqa: E402
    EXIT_INFO_GAP,
    append_gate_log,
    checks_path,
    load_checks_spec,
    validate_hierarchy_checks,
    write_validated_artifact,
)

GATE = "coi_hierarchy"
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

    write_validated_artifact(
        run_dir,
        {
            "status": "running",
            "validated_checks": [],
            "failed_checks": [],
            "producer": GATE,
        },
    )

    try:
        root = rtl_root(project_dir)
    except FileNotFoundError as exc:
        _finish(
            run_dir,
            log_path,
            status="failed",
            exit_code=EXIT_FAIL,
            validated=[],
            failed=[],
            evidence=[str(exc)],
        )
        return EXIT_FAIL

    if not (root / GEN_MARKER).is_file():
        msg = f"c-compile/gen prerequisite missing: {GEN_MARKER}"
        _finish(
            run_dir,
            log_path,
            status="failed",
            exit_code=EXIT_FAIL,
            validated=[],
            failed=[],
            evidence=[msg],
        )
        return EXIT_FAIL

    try:
        checks_path_resolved = checks_path(project_dir, run_dir)
        spec = load_checks_spec(checks_path_resolved)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        _finish(
            run_dir,
            log_path,
            status="failed",
            exit_code=EXIT_INFO_GAP,
            validated=[],
            failed=[],
            evidence=[str(exc)],
        )
        return EXIT_INFO_GAP

    filelist_rel = str(spec.get("filelist") or "filelists/eda/test/chip_top_example/manifest.list")
    filelist = root / filelist_rel
    if not filelist.is_file():
        msg = f"filelist not found: {filelist}"
        _finish(
            run_dir,
            log_path,
            status="failed",
            exit_code=EXIT_FAIL,
            validated=[],
            failed=[],
            evidence=[msg],
        )
        return EXIT_FAIL

    try:
        validated, failed = validate_hierarchy_checks(
            spec=spec,
            rtl_root=root,
            filelist=filelist,
            log_path=log_path,
        )
    except Exception as exc:  # noqa: BLE001 — gate boundary
        append_gate_log(log_path, f"hierarchy tool error: {exc}")
        _finish(
            run_dir,
            log_path,
            status="failed",
            exit_code=EXIT_TOOL_ERROR,
            validated=[],
            failed=[],
            evidence=[str(exc)],
        )
        return EXIT_TOOL_ERROR

    status = "complete"
    exit_code = EXIT_PASS if validated else EXIT_FAIL
    evidence = [
        f"hierarchy validated {len(validated)}/{len(spec.get('checks') or [])} check(s)",
    ]
    if failed:
        for item in failed[:6]:
            cid = str(item.get("id") or "?")
            errs = item.get("hierarchy_errors") or []
            evidence.append(f"{cid}: {' | '.join(errs)[:160]}")

    _finish(
        run_dir,
        log_path,
        status=status,
        exit_code=exit_code,
        validated=validated,
        failed=failed,
        evidence=evidence,
        checks_path=checks_path_resolved,
    )
    return exit_code


def _finish(
    run_dir: Path,
    log_path: Path,
    *,
    status: str,
    exit_code: int,
    validated: list[dict],
    failed: list[dict],
    evidence: list[str],
    checks_path: Path | None = None,
) -> None:
    artifact = {
        "status": status,
        "validated_checks": validated,
        "failed_checks": failed,
        "producer": GATE,
    }
    write_validated_artifact(run_dir, artifact)

    gate_status = "PASS" if exit_code == EXIT_PASS else ("INFO_GAP" if exit_code == EXIT_INFO_GAP else "FAIL")
    verdict: dict = {
        "gate": GATE,
        "status": gate_status,
        "exit_code": exit_code,
        "evidence": evidence,
        "artifacts": {
            "log": str(log_path),
            "validated": str(run_dir / "coi_hierarchy_validated.json"),
        },
        "hierarchy": {
            "validated": len(validated),
            "failed": len(failed),
        },
        "trust": {"script": "coi_hierarchy.py", "version": "0.1.0"},
    }
    if checks_path:
        verdict["artifacts"]["checks"] = str(checks_path)
    (run_dir / f"verdict_{GATE}.json").write_text(
        json.dumps(verdict, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())