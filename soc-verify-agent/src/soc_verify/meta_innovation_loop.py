"""Meta Innovation Loop — observe, BECI assess, 3-LLM consensus, intervene."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.beci_formula import assess_node_intervention, beci_vector_from_signals, rank_intervention_targets
from soc_verify.improvement_eval import collect_run_signals, load_history
from soc_verify.meta_graph import load_meta_spec
from soc_verify.models import load_yaml, save_yaml
from soc_verify.node_scorecard import collect_all_node_observations, iter_registered_nodes
from soc_verify.skill_registry import list_skills


SPEC_NAME = "meta_innovation_loop_spec.yaml"


def spec_path(root: Path) -> Path:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return p


def load_mil_spec(root: Path) -> dict[str, Any]:
    return load_yaml(spec_path(root)) or {}


def _mil_history_path(project_dir: Path) -> Path:
    d = project_dir / "meta_innovation"
    d.mkdir(parents=True, exist_ok=True)
    return d / "history.yaml"


def append_mil_history(project_dir: Path, record: dict[str, Any]) -> None:
    path = _mil_history_path(project_dir)
    data = load_yaml(path) if path.is_file() else {"contract": "meta_innovation_history_v1", "runs": []}
    data.setdefault("runs", []).append(record)
    save_yaml(path, data)


def collect_observations_payload(
    root: Path,
    project_dir: Path,
    *,
    recent_run_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    node_obs = collect_all_node_observations(project_dir, root)
    skills = list_skills(project_dir)
    recent_signals: list[dict[str, Any]] = []

    runs_root = project_dir / "runs"
    run_dirs = recent_run_dirs or []
    if not run_dirs and runs_root.is_dir():
        run_dirs = sorted(
            [p for p in runs_root.iterdir() if p.is_dir() and p.name != "setup"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:8]

    for rd in run_dirs:
        state_path = rd / "workflow_state.json"
        state: dict[str, Any] = {}
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        sig = collect_run_signals(rd, state)
        recent_signals.append(sig)

    return {
        "contract": "mil_observations_v1",
        "project_id": project_dir.name,
        "as_of": date.today().isoformat(),
        "node_observations": node_obs,
        "skills_registered": len(skills),
        "skills": [{"id": s.get("id"), "name": s.get("name")} for s in skills[:20]],
        "recent_run_signals": recent_signals,
        "meta_spec": str(spec_path(root)),
        "paper_artifacts": (load_mil_spec(root).get("paper_data") or {}).get("artifacts", []),
    }


def build_beci_assessment(
    root: Path,
    observations: dict[str, Any],
) -> dict[str, Any]:
    assessments: list[dict[str, Any]] = []
    for obs in observations.get("node_observations", {}).get("observations") or []:
        latest = obs.get("latest") or {}
        beci = latest.get("beci_vector") or latest.get("icbe_vector") or beci_vector_from_signals(latest)
        trend = {"urgency": float(obs.get("urgency_delta", 0.0))}
        a = assess_node_intervention(
            graph_id=str(obs.get("graph_id", "")),
            node_id=str(obs.get("node_id", "")),
            beci=beci,
            trend_delta=trend,
            root=root,
        )
        assessments.append(a.to_dict())

    for sig in observations.get("recent_run_signals") or []:
        beci = beci_vector_from_signals(sig)
        a = assess_node_intervention(
            graph_id="verify_group",
            node_id=f"{sig.get('stage', '')}/{sig.get('group', '')}",
            beci=beci,
            root=root,
        )
        assessments.append(a.to_dict())

    ranked = rank_intervention_targets(
        [assess_node_intervention(
            graph_id=a["graph_id"],
            node_id=a["node_id"],
            beci=a.get("beci") or a.get("icbe", {}),
            trend_delta=a.get("trend_delta"),
            root=root,
        ) for a in assessments]
    )
    spec = load_mil_spec(root)
    formula = spec.get("beci_formula") or spec.get("icbe_formula") or {}
    threshold = float(formula.get("intervene_threshold", 0.45))
    targets = [a.to_dict() for a in ranked if a.intervene]

    return {
        "contract": "mil_beci_assessment_v1",
        "threshold": threshold,
        "assessments": [a.to_dict() for a in ranked],
        "intervention_targets": targets[:10],
        "top_urgency": ranked[0].to_dict() if ranked else None,
    }


def write_skill_to_obsidian_prompt(run_dir: Path, project_dir: Path, skills: list[dict[str, Any]]) -> Path:
    payload = {
        "task": "skill_to_obsidian",
        "instruction": (
            "Convert user SKILL.md content into project-specific Obsidian MD under "
            "projects/{id}/knowledge/obsidian/. Preserve verification methodology; "
            "adapt paths/tags to this SoC project."
        ),
        "skills": skills,
        "required_outputs": [
            "projects/{id}/knowledge/obsidian/**/*.md",
            f"{run_dir.name}/skill_obsidian_manifest.json",
        ],
    }
    path = run_dir / "skill_to_obsidian_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_subagent_verify_prompt(
    run_dir: Path,
    *,
    assessment: dict[str, Any],
    skills: list[dict[str, Any]],
) -> Path:
    payload = {
        "task": "subagent_verify",
        "instruction": (
            "Read SKILL.md methodology. Pythonize runnable ops under projects/{id}/ops/. "
            "Dispatch sub-agent, observe process+result. Write subagent_verify.json."
        ),
        "intervention_targets": assessment.get("intervention_targets", []),
        "skills": skills,
        "required_outputs": ["subagent_verify.json"],
    }
    path = run_dir / "subagent_verify_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_multi_llm_review_prompt(run_dir: Path, assessment: dict[str, Any], *, root: Path) -> Path:
    roles = load_mil_spec(root).get("reviewer_roles") or [
        {"id": "reviewer_a"},
        {"id": "reviewer_b"},
        {"id": "reviewer_c"},
    ]
    payload = {
        "task": "multi_llm_review",
        "instruction": (
            "Three independent reviewers must each write reviewer_{a,b,c}.json with "
            "intervene: bool, target_node, rationale, evidence. No collusion — separate conclusions."
        ),
        "reviewer_roles": roles,
        "beci_assessment": assessment,
        "required_outputs": ["reviewer_a.json", "reviewer_b.json", "reviewer_c.json"],
    }
    path = run_dir / "multi_llm_review_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_reviews(run_dir: Path, *, min_reviews: int = 3) -> dict[str, Any]:
    spec_files = ["reviewer_a.json", "reviewer_b.json", "reviewer_c.json"]
    reviews: list[dict[str, Any]] = []
    issues: list[str] = []
    for fname in spec_files:
        path = run_dir / fname
        if not path.is_file():
            issues.append(f"missing {fname}")
            continue
        try:
            reviews.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            issues.append(f"invalid json: {fname}")

    if len(reviews) < min_reviews:
        issues.append(f"need>={min_reviews} reviews, got {len(reviews)}")
        return {"ok": False, "issues": issues, "reviews": reviews}

    intervene_votes = sum(1 for r in reviews if r.get("intervene"))
    targets = [r.get("target_node") for r in reviews if r.get("target_node")]
    majority_intervene = intervene_votes >= (len(reviews) // 2 + 1)
    target = max(set(targets), key=targets.count) if targets else ""

    return {
        "ok": True,
        "issues": issues,
        "reviews": reviews,
        "consensus": {
            "intervene": majority_intervene,
            "intervene_votes": intervene_votes,
            "total_reviews": len(reviews),
            "target_node": target,
            "policy": "majority_with_evidence",
        },
    }


def build_consensus_decision(run_dir: Path, review_result: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    consensus = review_result.get("consensus") or {}
    decision = {
        "contract": "meta_innovation_decision_v1",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "intervene": consensus.get("intervene", False),
        "target_node": consensus.get("target_node", ""),
        "intervention_targets": assessment.get("intervention_targets", []),
        "review_summary": {
            "votes": consensus.get("intervene_votes", 0),
            "total": consensus.get("total_reviews", 0),
        },
        "dispatch": [],
    }
    if decision["intervene"] and decision["target_node"]:
        decision["dispatch"] = [
            {
                "action": "route_to_node",
                "graph": decision["target_node"].split("/")[0] if "/" in decision["target_node"] else "verify_group",
                "node": decision["target_node"],
            }
        ]
    path = run_dir / "meta_innovation_decision.json"
    path.write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    return decision


def write_paper_data_prompt(run_dir: Path, project_dir: Path, decision: dict[str, Any], *, root: Path) -> Path:
    payload = {
        "task": "paper_data_maintain",
        "instruction": "Update paper campaign artifacts with this MIL run KPIs and decision evidence.",
        "decision": decision,
        "targets": load_mil_spec(root).get("paper_data", {}).get("artifacts", []),
        "required_outputs": ["paper_data_update.json"],
    }
    path = run_dir / "paper_data_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_paper_data_update(run_dir: Path) -> bool:
    return (run_dir / "paper_data_update.json").is_file()