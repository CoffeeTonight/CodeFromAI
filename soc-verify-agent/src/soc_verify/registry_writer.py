"""Registry writes — only after trust_eval + optional LLM promote_decision."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.constants import DEFAULT_TAU_PROMOTE_MIN
from soc_verify.models import PromoteDecision, load_yaml, save_yaml
from soc_verify.parity_eval import parity_allows_promote


def load_promote_decision(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "promote_decision.md"
    if not path.is_file():
        return {"decision": "defer", "reason": "no promote_decision.md"}
    text = path.read_text(encoding="utf-8")
    decision: PromoteDecision = "defer"
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("decision:"):
            val = low.split(":", 1)[1].strip()
            if val in ("approve", "defer", "reject"):
                decision = val  # type: ignore[assignment]
    return {"decision": decision, "raw": text}


def apply_promotion(
    project_dir: Path,
    script_name: str,
    *,
    trust_score: float,
    run_dir: Path,
    tau_promote_min: float = DEFAULT_TAU_PROMOTE_MIN,
    completeness_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    LLM proposes via promote_decision.md; this function is the only writer.
    approve AND trust >= tau_promote_min required.
    """
    promo = load_promote_decision(run_dir)
    decision = promo["decision"]

    reg_path = project_dir / "trust" / "registry.yaml"
    reg = load_yaml(reg_path)
    scripts = reg.setdefault("scripts", {})
    rec = scripts.setdefault(script_name, {"script": script_name})

    outcome = {
        "script": script_name,
        "llm_decision": decision,
        "trust_score": trust_score,
        "tau_promote_min": tau_promote_min,
        "promoted": False,
        "reason": "",
    }

    if decision == "reject":
        rec["status"] = "evaluated"
        outcome["reason"] = "llm_reject"
    elif decision == "defer":
        outcome["reason"] = "llm_defer"
    elif decision == "approve" and trust_score >= tau_promote_min:
        parity_ok, parity_reason = parity_allows_promote(run_dir)
        if not parity_ok:
            outcome["reason"] = parity_reason
        elif completeness_decision and not completeness_decision.get("promote_allowed", True):
            outcome["reason"] = "completeness_policy_blocked"
        else:
            rec["status"] = "canonical"
            rec["trust_score"] = trust_score
            rec["promoted_at"] = run_dir.name
            outcome["promoted"] = True
            outcome["reason"] = "approve_and_trust_ok"
    else:
        outcome["reason"] = "trust_below_min"

    scripts[script_name] = rec
    save_yaml(reg_path, reg)
    return outcome