"""Feedback rubric — user scores (optional) + auto question-sharpness scoring."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


USER_FEEDBACK_NAME = "user_feedback.json"
QUESTION_QUALITY_NAME = "question_quality.json"


def score_question_sharpness(question: dict[str, Any]) -> dict[str, Any]:
    """Auto-score LLM/platform question sharpness (1–5). Not a user score."""
    text = str(question.get("question", ""))
    qtype = str(question.get("type", ""))
    blocking = str(question.get("blocking", "no")).lower() == "yes"
    context = str(question.get("context", ""))

    score = 1.0
    reasons: list[str] = []

    if len(text) >= 40:
        score += 1.0
        reasons.append("specific_detail")
    elif len(text) >= 20:
        score += 0.5
        reasons.append("moderate_detail")

    if blocking:
        score += 1.0
        reasons.append("blocking")

    if context and "/" in context:
        score += 0.5
        reasons.append("stage_group_context")

    if qtype in ("stalemate", "bridge", "reproduction", "info"):
        score += 0.5
        reasons.append(f"type_{qtype}")

    if "?" in text or "provide" in text.lower() or "review" in text.lower():
        score += 0.5
        reasons.append("actionable")

    final = min(5.0, max(1.0, round(score, 2)))
    return {
        "question_id": question.get("id"),
        "sharpness_score": final,
        "scale": "1-5_auto",
        "scorer": "platform_heuristic",
        "reasons": reasons,
        "note": "Auto metric for LLM question quality — distinct from user_feedback",
    }


def score_all_questions(questions: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [score_question_sharpness(q) for q in questions if isinstance(q, dict)]
    avg = round(sum(s["sharpness_score"] for s in scored) / max(1, len(scored)), 2) if scored else 0.0
    return {
        "contract": "question_quality_v1",
        "as_of": date.today().isoformat(),
        "count": len(scored),
        "mean_sharpness": avg,
        "questions": scored,
    }


def write_question_quality(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / QUESTION_QUALITY_NAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_user_feedback(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / USER_FEEDBACK_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_user_feedback(
    run_dir: Path,
    *,
    overall_score: int,
    comment: str = "",
    dimension_scores: dict[str, int] | None = None,
    reviewer: str = "user",
) -> Path:
    """User-provided rubric (1–5). Optional — via CLI or manual file."""
    if not 1 <= overall_score <= 5:
        raise ValueError("overall_score must be 1–5")
    dims = dimension_scores or {}
    for k, v in dims.items():
        if not 1 <= int(v) <= 5:
            raise ValueError(f"dimension {k} must be 1–5")

    payload = {
        "contract": "user_feedback_v1",
        "as_of": date.today().isoformat(),
        "reviewer": reviewer,
        "overall_score": overall_score,
        "dimension_scores": dims,
        "comment": comment,
        "note": "Human rubric — distinct from question_sharpness auto-score",
    }
    path = run_dir / USER_FEEDBACK_NAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path