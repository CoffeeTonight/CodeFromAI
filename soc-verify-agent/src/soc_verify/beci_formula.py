"""BECI intervention formula — B/E/C/I; main-LLM decides where to intervene."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml


SPEC_NAME = "meta_innovation_loop_spec.yaml"


def spec_path(root: Path) -> Path:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return p


def load_beci_spec(root: Path) -> dict[str, Any]:
    return load_yaml(spec_path(root)) or {}


def beci_vector_from_signals(signals: dict[str, Any], events: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build BECI vector (B/E/C/I keys) compatible with branch_scorecard taxonomy."""
    events = events or {}
    gates = max(1, int(events.get("gates_run", 1)))
    completeness = float(signals.get("completeness", 0.0))
    error_kind = str(signals.get("error_kind", ""))
    return {
        "B": {
            "bridge_round": int(signals.get("bridge_round", 0)),
            "error_kind_bridge": error_kind == "tool",
            "rate": round(
                int(signals.get("bridge_round", 0)) / max(1, int(signals.get("fix_round", 0)) + 1),
                4,
            ),
        },
        "E": {
            "env_fail_steps": int(events.get("env_fail_steps", signals.get("env_fail_steps", 0))),
            "error_kind_env": error_kind in ("env", "tool"),
            "rate": round(int(events.get("env_fail_steps", signals.get("env_fail_steps", 0))) / gates, 4),
        },
        "C": {
            "completeness": completeness,
            "score": completeness,
            "deficit": round(1.0 - completeness, 4),
        },
        "I": {
            "info_interrupts": int(events.get("info_interrupts", 0)),
            "info_gap": bool(signals.get("info_gap")),
            "error_kind_info": error_kind == "info",
            "rate": round(int(events.get("info_interrupts", 0)) / gates, 4),
        },
    }


@dataclass
class InterventionAssessment:
    node_id: str
    graph_id: str
    urgency: float
    intervene: bool
    beci: dict[str, Any]
    trend_delta: dict[str, float] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "graph_id": self.graph_id,
            "urgency": self.urgency,
            "intervene": self.intervene,
            "beci": self.beci,
            "trend_delta": self.trend_delta,
            "rationale": self.rationale,
        }


def compute_intervention_urgency(
    beci: dict[str, Any],
    *,
    trend_delta: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
    trend_boost: float = 0.15,
) -> float:
    w = weights or {"B": 0.20, "E": 0.25, "C": 0.30, "I": 0.25}
    b_rate = float(beci.get("B", {}).get("rate", 0.0))
    e_rate = float(beci.get("E", {}).get("rate", 0.0))
    c_deficit = float(beci.get("C", {}).get("deficit", 1.0 - beci.get("C", {}).get("score", 0.0)))
    i_rate = float(beci.get("I", {}).get("rate", 0.0))
    base = (
        w.get("B", 0.2) * b_rate
        + w.get("E", 0.25) * e_rate
        + w.get("C", 0.3) * c_deficit
        + w.get("I", 0.25) * i_rate
    )
    trend = 0.0
    if trend_delta:
        negatives = [v for v in trend_delta.values() if v < 0]
        if negatives:
            trend = abs(sum(negatives) / len(negatives))
    return round(min(1.0, max(0.0, base + trend_boost * trend)), 4)


def assess_node_intervention(
    *,
    graph_id: str,
    node_id: str,
    beci: dict[str, Any],
    trend_delta: dict[str, float] | None = None,
    root: Path | None = None,
) -> InterventionAssessment:
    spec = load_beci_spec(root) if root else {}
    formula = spec.get("beci_formula") or spec.get("icbe_formula") or {}
    weights = formula.get("weights") or {}
    threshold = float(formula.get("intervene_threshold", 0.45))
    urgency = compute_intervention_urgency(
        beci,
        trend_delta=trend_delta,
        weights=weights,
        trend_boost=float(formula.get("trend_boost", 0.15)),
    )
    intervene = urgency >= threshold
    parts: list[str] = []
    if beci.get("B", {}).get("rate", 0) > 0.3:
        parts.append("B-high")
    if beci.get("E", {}).get("rate", 0) > 0.2:
        parts.append("E-high")
    if beci.get("C", {}).get("deficit", 0) > 0.3:
        parts.append("C-high")
    if beci.get("I", {}).get("rate", 0) > 0.2:
        parts.append("I-high")
    return InterventionAssessment(
        node_id=node_id,
        graph_id=graph_id,
        urgency=urgency,
        intervene=intervene,
        beci=beci,
        trend_delta=dict(trend_delta or {}),
        rationale="; ".join(parts) if parts else "within_threshold",
    )


def rank_intervention_targets(assessments: list[InterventionAssessment]) -> list[InterventionAssessment]:
    return sorted(assessments, key=lambda a: a.urgency, reverse=True)