"""LangGraph state for meta_innovation_loop."""

from __future__ import annotations

from typing import Any, TypedDict


class MetaInnovationState(TypedDict, total=False):
    root: str
    project_id: str
    project_dir: str
    run_id: str
    as_of: str
    trigger_reason: str

    observations: dict[str, Any]
    beci_assessment: dict[str, Any]
    review_result: dict[str, Any]
    decision: dict[str, Any]

    consensus_ok: bool
    verdict: str
    events: dict[str, Any]