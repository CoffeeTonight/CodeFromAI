"""Classify errors into e/t/i/l — code only, not LLM."""

from __future__ import annotations

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


def classify_stop_report(report: dict[str, Any]) -> ErrorKind:
    reason = str(report.get("stop_reason", "")).lower()
    if "info" in reason or "missing" in reason or "gap" in reason:
        return "info"
    if "license" in reason or "path" in reason or "env" in reason:
        return "env"
    if "tool" in reason or "script" in reason or "syntax" in reason:
        return "tool"
    if "hallucin" in reason or "no_tool" in reason:
        return "llm"
    return "env"


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