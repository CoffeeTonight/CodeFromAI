"""LangGraph state for setup_group — adaptive project onboarding."""

from __future__ import annotations

from typing import Any, TypedDict


class SetupGroupState(TypedDict, total=False):
    root: str
    project_id: str
    project_dir: str
    run_id: str
    as_of: str

    user_skillset: str
    milestone_plan: str
    current_milestone: str
    milestone_context: dict[str, Any]

    skills_registered: int
    skill_ids: list[str]
    materialized_groups: list[dict[str, Any]]
    setup_adapt: dict[str, Any]
    bootstrap_ok: bool
    ops_bootstrapped: list[dict[str, Any]]
    verify_smoke_verdict: str
    verify_smoke_result: dict[str, Any]

    verdict: str
    error: str
    events: dict[str, Any]