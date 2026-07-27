"""Platform-minimal weakness mining — used when project ops lack full self-harness."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

WEAKNESS_REPORT = "weakness_report.json"
SPEC_NAME = "self_harness_spec.yaml"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _spec_path(root: Path) -> Path:
    p = root / "registry" / SPEC_NAME
    if p.is_file():
        return p
    return Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME


def _read_graph_trace(run_dir: Path) -> list[dict[str, Any]]:
    trace_path = run_dir / "graph_trace.jsonl"
    if not trace_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _find_verdict(run_dir: Path, group: str) -> dict[str, Any] | None:
    if group:
        named = run_dir / f"verdict_{group}.json"
        if named.is_file():
            return _load_json(named)
    for path in sorted(run_dir.glob("verdict_*.json")):
        data = _load_json(path)
        if data:
            return data
    return _load_json(run_dir / "verdict.json")


def _weakness(
    *,
    category: str,
    summary: str,
    evidence: list[str],
    severity: str = "medium",
) -> dict[str, Any]:
    return {
        "category": category,
        "summary": summary,
        "evidence": evidence,
        "severity": severity,
    }


def mine_weaknesses(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    signals: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mine structured weaknesses from run artifacts (platform-minimal)."""
    spec = load_yaml(_spec_path(root)) if _spec_path(root).is_file() else {}
    signals = dict(signals or _load_json(run_dir / "improvement_signal.json") or {})
    snapshot = dict(snapshot or _load_json(run_dir / "improvement_snapshot.json") or {})
    stage = str(signals.get("stage") or snapshot.get("stage") or "")
    group = str(signals.get("group") or snapshot.get("group") or "")
    weaknesses: list[dict[str, Any]] = []

    sub_stop = _load_json(run_dir / "sub_stop.json")
    if sub_stop:
        weaknesses.append(
            _weakness(
                category="tool_artifact",
                summary=str(sub_stop.get("reason") or sub_stop.get("message") or "sub_stop halted graph"),
                evidence=[f"runs/{run_dir.name}/sub_stop.json"],
                severity="high",
            )
        )

    if int(signals.get("env_fail_steps") or 0) >= 2:
        weaknesses.append(
            _weakness(
                category="env_loop",
                summary="Repeated environment failures before gate success",
                evidence=[f"env_fail_steps={signals.get('env_fail_steps')}"],
            )
        )

    if signals.get("stalemate"):
        pattern = str(signals.get("stalemate_pattern") or "")
        cat = "stalemate_oscillation" if pattern == "OSCILLATION" else "stalemate_spin"
        weaknesses.append(
            _weakness(
                category=cat,
                summary=f"Loop guard stalemate ({pattern or 'unknown'})",
                evidence=[f"stalemate_pattern={pattern}"],
            )
        )

    verdict = _find_verdict(run_dir, group)
    if verdict:
        info_gap = verdict.get("info_gap") or verdict.get("INFO_GAP")
        if isinstance(info_gap, dict) and info_gap.get("fields"):
            weaknesses.append(
                _weakness(
                    category="info_gap",
                    summary="Verdict reports missing intake fields",
                    evidence=[str(info_gap.get("fields"))],
                )
            )
        if str(verdict.get("verdict") or "").upper() == "FAIL":
            weaknesses.append(
                _weakness(
                    category="verification_gap",
                    summary=str(verdict.get("summary") or "Gate verdict FAIL"),
                    evidence=[f"runs/{run_dir.name}/verdict_{group or '*'}.json"],
                )
            )

    if signals.get("parity_ok") is False:
        weaknesses.append(
            _weakness(
                category="parity_block",
                summary="Python vs LLM parity mismatch",
                evidence=["parity_ok=false"],
            )
        )

    if int(signals.get("llm_fix_rounds") or 0) >= 3 and str(signals.get("verdict")) != "PASS":
        weaknesses.append(
            _weakness(
                category="llm_inefficiency",
                summary="Multiple LLM fix rounds without PASS",
                evidence=[f"llm_fix_rounds={signals.get('llm_fix_rounds')}"],
            )
        )

    if signals.get("promoted") is False and str(signals.get("verdict")) == "PASS":
        weaknesses.append(
            _weakness(
                category="promote_block",
                summary="PASS without promote_outcome.promoted",
                evidence=["promoted=false"],
            )
        )

    trace = _read_graph_trace(run_dir)
    validation_nodes = [r for r in trace if str(r.get("node", "")).startswith("validation")]
    if validation_nodes and str(signals.get("verdict")) != "PASS":
        weaknesses.append(
            _weakness(
                category="validation_stall",
                summary="Validation subgraph active without final PASS",
                evidence=[f"validation_nodes={len(validation_nodes)}"],
            )
        )

    return {
        "contract": "weakness_report_v1",
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "mined_at": datetime.now(timezone.utc).isoformat(),
        "weaknesses": weaknesses,
        "categories_allowed": list(spec.get("weakness_categories") or []),
        "source": "platform_minimal",
    }


def write_weakness_report(run_dir: Path, report: dict[str, Any]) -> Path:
    path = run_dir / WEAKNESS_REPORT
    _write_json(path, report)
    return path