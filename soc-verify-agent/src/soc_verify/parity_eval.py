"""LLM tool-run vs Python ops parity — mandatory before canonical promote."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


LLM_REFERENCE_NAME = "llm_reference_verdict.json"
PARITY_REPORT_NAME = "parity_report.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_llm_reference(run_dir: Path, group: str) -> Path:
    """Freeze LLM tool-run verdict as parity reference (A side)."""
    src = run_dir / f"verdict_{group}.json"
    dst = run_dir / LLM_REFERENCE_NAME
    if not src.is_file():
        raise FileNotFoundError(f"missing LLM verdict: {src}")
    shutil.copy2(src, dst)
    return dst


def _compare_field(path: str, a: Any, b: Any) -> list[str]:
    issues: list[str] = []
    if a != b:
        issues.append(f"{path}: llm={a!r} python={b!r}")
    return issues


def compare_verdicts(reference: dict[str, Any], python: dict[str, Any]) -> dict[str, Any]:
    """Structural parity check — A (LLM) vs B (Python ops)."""
    issues: list[str] = []

    issues.extend(_compare_field("status", reference.get("status"), python.get("status")))

    ref_scan = reference.get("log_scan") or {}
    py_scan = python.get("log_scan") or {}
    if ref_scan or py_scan:
        issues.extend(_compare_field("log_scan.ok", ref_scan.get("ok"), py_scan.get("ok")))

    ref_conn = reference.get("connectivity") or {}
    py_conn = python.get("connectivity") or {}
    if ref_conn or py_conn:
        if set(ref_conn) != set(py_conn):
            issues.append(f"connectivity.keys: llm={sorted(ref_conn)} python={sorted(py_conn)}")
        else:
            for cid in ref_conn:
                r, p = ref_conn[cid], py_conn.get(cid, {})
                if isinstance(r, dict) and isinstance(p, dict):
                    issues.extend(
                        _compare_field(f"connectivity.{cid}.connected", r.get("connected"), p.get("connected"))
                    )

    ref_tiers = (reference.get("artifacts") or {}).get("tiers") or reference.get("tiers") or {}
    py_tiers = (python.get("artifacts") or {}).get("tiers") or python.get("tiers") or {}
    if ref_tiers or py_tiers:
        if set(ref_tiers) != set(py_tiers):
            issues.append(f"tiers.keys: llm={sorted(ref_tiers)} python={sorted(py_tiers)}")
        else:
            for tid in ref_tiers:
                rt, pt = ref_tiers[tid], py_tiers.get(tid, {})
                if isinstance(rt, dict) and isinstance(pt, dict):
                    issues.extend(_compare_field(f"tiers.{tid}.ok", rt.get("ok"), pt.get("ok")))

    ok = not issues
    return {
        "ok": ok,
        "issues": issues,
        "reference_status": reference.get("status"),
        "python_status": python.get("status"),
        "contract": "parity_eval_v1",
    }


def write_parity_report(run_dir: Path, report: dict[str, Any]) -> Path:
    path = run_dir / PARITY_REPORT_NAME
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_parity_report(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / PARITY_REPORT_NAME
    if not path.is_file():
        return None
    return _load_json(path)


def parity_allows_promote(run_dir: Path) -> tuple[bool, str]:
    report = load_parity_report(run_dir)
    if report is None:
        return False, "missing_parity_report"
    if not report.get("ok"):
        return False, "parity_not_ok"
    return True, "parity_ok"


def run_parity_check(
    run_dir: Path,
    group: str,
    *,
    python_verdict: dict[str, Any],
) -> dict[str, Any]:
    ref_path = run_dir / LLM_REFERENCE_NAME
    if not ref_path.is_file():
        return {
            "ok": False,
            "issues": ["missing llm_reference_verdict.json — run llm_tools PASS first"],
            "contract": "parity_eval_v1",
        }
    reference = _load_json(ref_path)
    report = compare_verdicts(reference, python_verdict)
    write_parity_report(run_dir, report)
    return report