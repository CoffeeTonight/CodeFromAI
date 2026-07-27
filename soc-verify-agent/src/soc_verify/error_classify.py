"""Classify errors into e/t/i/l — code only, not LLM."""

from __future__ import annotations

import re
from typing import Any, Literal

from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_INFO_GAP, EXIT_TOOL_ERROR

ErrorKind = Literal["env", "tool", "info", "llm", "verification", "none"]

_BUMP_KINDS = frozenset({"env", "tool", "info", "llm", "verification"})


def classify_exit_code(exit_code: int) -> ErrorKind:
    if exit_code == EXIT_INFO_GAP:
        return "info"
    if exit_code == EXIT_TOOL_ERROR:
        return "tool"
    if exit_code == EXIT_FAIL:
        return "verification"
    if exit_code == EXIT_BLOCKED:
        return "env"
    return "none"


def resolve_bump_kind(fail_kind: ErrorKind, *, exit_code: int | None = None) -> ErrorKind:
    """Map a gate failure kind to an event counter bucket."""
    if fail_kind in _BUMP_KINDS:
        return fail_kind
    if exit_code is not None:
        return classify_exit_code(exit_code)
    return "verification"


def _classify_error_code(code: str) -> ErrorKind:
    c = code.strip().lower()
    if c in ("4", "info", "info_gap", "exit_info_gap"):
        return "info"
    if c in ("3", "tool", "tool_error", "exit_tool_error"):
        return "tool"
    if c in ("2", "blocked", "env", "exit_blocked"):
        return "env"
    if c in ("hallucin", "no_tool", "llm"):
        return "llm"
    if c in ("1", "fail", "verification", "exit_fail"):
        return "verification"
    return "none"


def _reason_has_token(reason: str, token: str) -> bool:
    if token.isalpha():
        return bool(re.search(rf"\b{re.escape(token)}\b", reason))
    return token in reason


def classify_stop_report(report: dict[str, Any]) -> ErrorKind:
    code = str(report.get("error_code", "")).strip()
    if code:
        mapped = _classify_error_code(code)
        if mapped != "none":
            return mapped

    partial = str(report.get("partial_verdict", "")).upper()
    if partial == "INFO_GAP":
        return "info"

    reason = str(report.get("stop_reason", "")).lower()
    if any(_reason_has_token(reason, t) for t in ("license", "path", "env", "blocked")):
        return "env"
    if _reason_has_token(reason, "info_gap"):
        return "info"
    if any(_reason_has_token(reason, t) for t in ("tool", "script", "syntax")):
        return "tool"
    if any(_reason_has_token(reason, t) for t in ("hallucin", "no_tool", "llm")):
        return "llm"
    if any(_reason_has_token(reason, t) for t in ("verification", "verif", "fail", "gate")):
        return "verification"
    return "verification"


def bump_events(events: dict[str, Any], kind: ErrorKind) -> dict[str, Any]:
    events = dict(events)
    events["total_steps"] = int(events.get("total_steps", 0)) + 1
    events["fix_rounds"] = int(events.get("fix_rounds", 0)) + 1
    if kind == "env":
        events["env_fail_steps"] = int(events.get("env_fail_steps", 0)) + 1
    elif kind == "tool":
        events["tool_incidents"] = int(events.get("tool_incidents", 0)) + 1
    elif kind == "info":
        events["info_interrupts"] = int(events.get("info_interrupts", 0)) + 1
    elif kind == "llm":
        events["llm_fix_rounds"] = int(events.get("llm_fix_rounds", 0)) + 1
    elif kind == "verification":
        events["verification_fail_steps"] = int(events.get("verification_fail_steps", 0)) + 1
    return events