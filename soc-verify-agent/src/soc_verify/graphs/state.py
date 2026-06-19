"""LangGraph state for verify_group."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class VerifyGroupState(TypedDict, total=False):
    project_id: str
    project_dir: str
    stage: str
    group: str
    run_id: str
    as_of: str
    orchestrator_run_id: str
    group_context: dict[str, Any]

    runner: Literal["python", "llm"]
    runner_mode: str  # python_canonical | llm_tools | llm_codegen
    force_mode: str  # llm_full when stalemate
    script_name: str
    parity_ok: bool
    codegen_round: int
    bridge_round: int
    error_kind: str  # env | tool | info | llm | verification | none

    round: int
    fix_round: int
    verdict: Literal["PASS", "FAIL", "BLOCKED", "INFO_GAP"]
    gate_results: dict[str, str]
    trust_score: float

    open_issues: int
    completeness: float
    events: dict[str, Any]

    stalemate: bool
    info_gap: bool
    info_gap_message: str

    sub_stop: dict[str, Any]
    questions: Annotated[list[dict[str, Any]], operator.add]

    promote_outcome: dict[str, Any]
    error: str

    improvement_index: float
    meta_queued: bool
    jira_allowed: bool
    continue_improvement: bool

    # Paper factory experiment tags
    experiment_campaign: str
    experiment_condition: str
    experiment_hypothesis: str

    # SoC validation autonomy (goal items, not IP coverage)
    validation_needs_judgment: bool
    validation_sequence_action: str
    validation_continue: bool