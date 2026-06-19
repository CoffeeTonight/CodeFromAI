"""Evidence gates for child-graph steps — input / procedural / output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.meta_graph import load_meta_proposal, validate_meta_proposal
from soc_verify.meta_graph import load_meta_spec as _load_meta_spec
from soc_verify.models import load_yaml
from soc_verify.node_contract import build_contract_context, _eval_check_any_of


@dataclass
class EvidenceResult:
    step_id: str
    ok: bool
    input_ok: bool
    procedural_ok: bool
    output_ok: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "ok": self.ok,
            "input_ok": self.input_ok,
            "procedural_ok": self.procedural_ok,
            "output_ok": self.output_ok,
            "issues": self.issues,
        }


def _resolve_template(path: str, ctx: dict[str, Any]) -> str:
    return path.format(**ctx)


def _eval_custom_check(
    check: dict[str, Any],
    *,
    ctx: dict[str, Any],
    state: dict[str, Any],
    run_dir: Path,
    root: Path,
) -> list[str]:
    ctype = check.get("type", "")
    if ctype == "any_of":
        subs = check.get("checks") or []
        for sub in subs:
            if isinstance(sub, dict) and not _eval_custom_check(
                sub, ctx=ctx, state=state, run_dir=run_dir, root=root
            ):
                return []
        return [f"any_of: no branch satisfied ({len(subs)} checks)"]

    if ctype in ("file_exists", "json_field_true", "json_field_equals"):
        return _eval_check_any_of(check, ctx)

    if ctype == "state_field_set":
        field_name = str(check.get("field", ""))
        if not state.get(field_name):
            return [f"state.{field_name} not set"]
        return []

    if ctype == "state_field_equals":
        field_name = str(check.get("field", ""))
        expected = check.get("value")
        actual = state.get(field_name)
        if actual != expected:
            return [f"state.{field_name}: expected {expected!r}, got {actual!r}"]
        return []

    if ctype == "state_field_in":
        field_name = str(check.get("field", ""))
        allowed = set(check.get("values") or [])
        actual = state.get(field_name)
        if actual not in allowed:
            return [f"state.{field_name}: {actual!r} not in {sorted(allowed)}"]
        return []

    if ctype == "state_field_gt":
        field_name = str(check.get("field", ""))
        threshold = check.get("value", 0)
        try:
            actual = int(state.get(field_name, 0))
        except (TypeError, ValueError):
            return [f"state.{field_name}: not numeric"]
        if actual <= int(threshold):
            return [f"state.{field_name}: {actual} <= {threshold}"]
        return []

    if ctype == "json_field_false":
        path = check.get("path", "")
        from soc_verify.node_contract import _resolve_path

        fpath = _resolve_path(str(path), ctx)
        field_name = str(check.get("field", "ok"))
        if not fpath.is_file():
            return [f"missing json: {fpath}"]
        data = json.loads(fpath.read_text(encoding="utf-8"))
        if data.get(field_name):
            return [f"{fpath.name}.{field_name} is true"]
        return []

    if ctype == "trace_contains":
        node = str(check.get("node", ""))
        trace_path = run_dir / "graph_trace.jsonl"
        if not trace_path.is_file():
            return [f"graph_trace missing; need node {node}"]
        found = False
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if str(json.loads(line).get("node", "")) == node:
                    found = True
                    break
            except json.JSONDecodeError:
                continue
        if not found:
            return [f"trace missing node: {node}"]
        return []

    if ctype == "error_kind_in":
        allowed = set(check.get("values") or [])
        kind = str(state.get("error_kind", ""))
        if kind not in allowed:
            return [f"error_kind {kind!r} not in {sorted(allowed)}"]
        return []

    if ctype == "events_bumped":
        events = state.get("events") or {}
        field_name = str(check.get("field", "gates_run"))
        if int(events.get(field_name, 0)) < 1:
            return [f"events.{field_name} < 1"]
        return []

    if ctype == "round_under_max":
        field_name = str(check.get("field", "codegen_round"))
        max_key = str(check.get("max_key", ""))
        policies = load_yaml(root / "registry" / "policies.yaml")
        parts = max_key.split(".")
        cur: Any = policies
        for p in parts:
            cur = (cur or {}).get(p) if isinstance(cur, dict) else None
        max_val = int(cur or 99)
        if int(state.get(field_name, 0)) > max_val:
            return [f"{field_name} {state.get(field_name)} > max {max_val}"]
        return []

    if ctype == "policy_true":
        rel = str(check.get("path", ""))
        key = str(check.get("key", ""))
        data = load_yaml(root / rel)
        cur: Any = data
        for p in key.split("."):
            cur = (cur or {}).get(p) if isinstance(cur, dict) else None
        if not cur:
            return [f"policy {key} not true"]
        return []

    if ctype == "parity_ok_or_skip":
        if state.get("parity_ok") is True:
            return []
        report = run_dir / "parity_report.json"
        if report.is_file():
            try:
                if json.loads(report.read_text(encoding="utf-8")).get("ok"):
                    return []
            except json.JSONDecodeError:
                pass
        if state.get("runner") == "python":
            return []
        return ["parity not ok"]

    if ctype == "meta_proposal_valid":
        proposal = load_meta_proposal(run_dir)
        if not proposal:
            return ["no meta_change_proposal.json"]
        spec = _load_meta_spec(root)
        if not validate_meta_proposal(proposal, spec).get("ok"):
            return ["meta proposal validation failed"]
        return []

    return [f"unknown evidence check: {ctype}"]


def _eval_evidence_group(
    checks: list[dict[str, Any]],
    *,
    ctx: dict[str, Any],
    state: dict[str, Any],
    run_dir: Path,
    root: Path,
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    for check in checks:
        issues.extend(
            _eval_custom_check(check, ctx=ctx, state=state, run_dir=run_dir, root=root)
        )
    return (not issues, issues)


def validate_step_evidence(
    step: dict[str, Any],
    *,
    root: Path,
    graph_id: str,
    state: dict[str, Any],
    run_dir: Path,
) -> EvidenceResult:
    step_id = str(step.get("id", ""))
    evidence = step.get("evidence") or {}
    ctx = build_contract_context(root=root, graph_id=graph_id, state=state, run_dir=run_dir)

    input_ok, input_issues = _eval_evidence_group(
        list(evidence.get("input") or []),
        ctx=ctx,
        state=state,
        run_dir=run_dir,
        root=root,
    )
    proc_ok, proc_issues = _eval_evidence_group(
        list(evidence.get("procedural") or []),
        ctx=ctx,
        state=state,
        run_dir=run_dir,
        root=root,
    )
    out_ok, out_issues = _eval_evidence_group(
        list(evidence.get("output") or []),
        ctx=ctx,
        state=state,
        run_dir=run_dir,
        root=root,
    )
    issues = (
        [f"input:{x}" for x in input_issues]
        + [f"procedural:{x}" for x in proc_issues]
        + [f"output:{x}" for x in out_issues]
    )
    ok = input_ok and proc_ok and out_ok
    return EvidenceResult(
        step_id=step_id,
        ok=ok,
        input_ok=input_ok,
        procedural_ok=proc_ok,
        output_ok=out_ok,
        issues=issues,
    )