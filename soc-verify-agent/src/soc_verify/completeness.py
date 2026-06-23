"""Verification completeness: (1-e)(1-t)(1-l) + info_unresolved flag + policy gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CompletenessMetrics:
    e: float
    t: float
    i: float
    l: float
    env_fail_steps: int = 0
    unresolved_env: int = 0
    tool_incidents: int = 0
    info_interrupts: int = 0
    info_unresolved: int = 0
    llm_fix_rounds: int = 0
    fix_rounds: int = 0
    total_steps: int = 1
    gates_run: int = 1
    max_rounds: int = 20
    fail_fast_stops: int = 0
    one_shot: bool = False

    @property
    def score(self) -> float:
        """Continuous score — info gap is a separate hard-stop flag, not a multiplier."""
        raw = (1 - self.e) * (1 - self.t) * (1 - self.l)
        return max(0.0, min(1.0, raw))

    def to_dict(self) -> dict[str, Any]:
        return {
            "e": round(self.e, 4),
            "t": round(self.t, 4),
            "i": round(self.i, 4),
            "l": round(self.l, 4),
            "completeness": round(self.score, 4),
            "fail_fast_stops": self.fail_fast_stops,
            "one_shot": self.one_shot,
            "unresolved_env": self.unresolved_env,
            "info_unresolved": self.info_unresolved,
        }

    @classmethod
    def from_events(cls, events: dict[str, Any]) -> CompletenessMetrics:
        gates = max(int(events.get("gates_run", 1)), 1)
        fix_rounds = int(events.get("fix_rounds", events.get("llm_fix_rounds", 0)))

        unresolved_env = int(events.get("unresolved_env", events.get("env_fail_steps", 0)))
        e = unresolved_env / gates

        t = int(events.get("tool_incidents", 0)) / gates

        info_unresolved = int(events.get("info_unresolved", events.get("info_interrupts", 0)))
        i = 1.0 if info_unresolved > 0 else 0.0

        llm_fix = int(events.get("llm_fix_rounds", 0))
        l = llm_fix / max(1, fix_rounds + 1)

        return cls(
            e=min(e, 1.0),
            t=min(t, 1.0),
            i=i,
            l=min(l, 1.0),
            env_fail_steps=int(events.get("env_fail_steps", 0)),
            unresolved_env=unresolved_env,
            tool_incidents=int(events.get("tool_incidents", 0)),
            info_interrupts=int(events.get("info_interrupts", 0)),
            info_unresolved=info_unresolved,
            llm_fix_rounds=llm_fix,
            fix_rounds=fix_rounds,
            total_steps=int(events.get("total_steps", 1)),
            gates_run=gates,
            max_rounds=int(events.get("max_rounds", 20)),
            fail_fast_stops=int(events.get("fail_fast_stops", 0)),
            one_shot=bool(events.get("one_shot", False)),
        )


@dataclass
class CompletenessDecision:
    jira_allowed: bool
    jira_note: str
    promote_allowed: bool
    promote_reason: str
    continue_improvement: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "jira_allowed": self.jira_allowed,
            "jira_note": self.jira_note,
            "promote_allowed": self.promote_allowed,
            "promote_reason": self.promote_reason,
            "continue_improvement": self.continue_improvement,
        }


def _promotion_hardening_ok(
    metrics: CompletenessMetrics,
    policies: dict[str, Any],
    *,
    trust_runs: int,
) -> tuple[bool, str]:
    promo = policies.get("promotion") or {}
    min_gates = int(promo.get("min_gates_before_promote", 3))
    min_trust_runs = int(promo.get("min_trust_runs", 3))
    if metrics.gates_run < min_gates:
        return False, f"min_gates:{metrics.gates_run}<{min_gates}"
    if trust_runs < min_trust_runs:
        return False, f"min_trust_runs:{trust_runs}<{min_trust_runs}"
    return True, "ok"


def evaluate_completeness_policy(
    metrics: CompletenessMetrics,
    policies: dict[str, Any],
    *,
    verdict: str = "FAIL",
    trust_score: float = 0.0,
    tau_promote_min: float = 0.70,
    trust_runs: int = 0,
) -> CompletenessDecision:
    comp = policies.get("completeness") or {}
    th = comp.get("thresholds") or {}

    jira_min = float(th.get("jira_complete_min", 0.80))
    healthy_min = float(th.get("healthy_complete_min", 0.90))
    promote_min = float(th.get("promote_min", 0.85))
    max_t = float(th.get("promote_max_t", 0.10))
    max_l = float(th.get("promote_max_l", 0.15))
    withhold_note = str(th.get("withhold_jira_note", "needs_hardening"))

    c = metrics.score

    if metrics.info_unresolved > 0:
        return CompletenessDecision(
            jira_allowed=False,
            jira_note="info_gap_unresolved",
            promote_allowed=False,
            promote_reason="info_unresolved",
            continue_improvement=True,
        )

    hardening_ok, hardening_reason = _promotion_hardening_ok(
        metrics, policies, trust_runs=trust_runs
    )

    jira_allowed = verdict == "PASS" and c >= jira_min and hardening_ok
    jira_note = ""
    if verdict == "PASS" and c < jira_min:
        jira_note = "withhold_complete_below_threshold"
    elif verdict == "PASS" and jira_min <= c < healthy_min:
        jira_note = withhold_note
    elif verdict == "PASS" and not hardening_ok:
        jira_note = hardening_reason

    promote_allowed = (
        verdict == "PASS"
        and hardening_ok
        and trust_score >= tau_promote_min
        and c >= promote_min
        and metrics.t <= max_t
        and metrics.l <= max_l
    )
    promote_reason = "ok" if promote_allowed else (
        hardening_reason if not hardening_ok else "threshold_not_met"
    )

    # Low C does NOT stop — next round uses llm runner (see select_runner).
    # continue_improvement: keep looping until PASS + C >= jira_min + min gate/trust runs.
    continue_improvement = (
        verdict != "PASS"
        or (verdict == "PASS" and c < jira_min)
        or (verdict == "PASS" and not hardening_ok)
    )

    return CompletenessDecision(
        jira_allowed=jira_allowed,
        jira_note=jira_note,
        promote_allowed=promote_allowed,
        promote_reason=promote_reason,
        continue_improvement=continue_improvement,
    )