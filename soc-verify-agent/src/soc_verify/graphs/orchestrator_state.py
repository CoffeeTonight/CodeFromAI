"""LangGraph state for top-level orchestrator."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class WorkItem(TypedDict, total=False):
    kind: Literal["acquisition", "verify"]
    acq: Literal[
        "project_search",
        "project_intake",
        "knowledge_collect",
        "state_sync",
        "tag_watch",
    ]
    project_id: str
    stage: str
    group: str


class OrchestratorState(TypedDict, total=False):
    root: str
    run_id: str
    as_of: str
    mode: Literal["workspace", "single_verify"]

    # single-verify target (optional)
    project_id: str
    stage: str
    group: str

    work_queue: list[WorkItem]
    work_index: int
    current_work: WorkItem

    acquisition_log: Annotated[list[dict[str, Any]], operator.add]
    verify_results: Annotated[list[dict[str, Any]], operator.add]

    group_context: dict[str, Any]
    info_gap: bool
    info_gap_message: str
    verdict: str
    error: str

    experiment_campaign: str
    experiment_condition: str
    experiment_hypothesis: str