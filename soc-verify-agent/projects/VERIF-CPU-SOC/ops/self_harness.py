"""Self-Harness loop — weakness mining, harness proposals, validation scaffold (Phase B)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

NEVER_AUTO_APPLY_LAYERS = frozenset({"skill", "verification_md", "graph_source"})

SPEC_NAME = "self_harness_spec.yaml"
WEAKNESS_REPORT = "weakness_report.json"
HARNESS_PROPOSAL = "harness_proposal.json"
HARNESS_PROPOSAL_LLM = "harness_proposal_llm.json"
HARNESS_VALIDATION = "harness_validation.json"
HARNESS_HELD_OUT_VALIDATION = "harness_held_out_validation.json"
HARNESS_LLM_PROMPT = "harness_llm_prompt.json"


def _repo_root(project_dir: Path) -> Path:
    return project_dir.parent.parent


def spec_path(root: Path) -> Path:
    p = root / "registry" / SPEC_NAME
    if p.is_file():
        return p
    return Path(__file__).resolve().parents[3] / "registry" / SPEC_NAME


def load_yaml(path: Path) -> dict[str, Any]:
    if path.is_file() and yaml is not None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    json_path = path.with_suffix(".json") if path.suffix == ".yaml" else path
    if json_path.is_file():
        return _load_json(json_path) or {}
    return {}


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return
    json_path = path.with_suffix(".json") if path.suffix == ".yaml" else path
    _write_json(json_path, data)


def load_spec(root: Path) -> dict[str, Any]:
    return load_yaml(spec_path(root))


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_graph_trace(run_dir: Path) -> list[dict[str, Any]]:
    trace_path = run_dir / "graph_trace.jsonl"
    if not trace_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _find_verdict(run_dir: Path, group: str) -> dict[str, Any] | None:
    if group:
        named = run_dir / f"verdict_{group}.json"
        if named.is_file():
            return _load_json(named)
    for path in sorted(run_dir.glob("verdict_*.json")):
        data = _load_json(path)
        if data:
            return data
    return _load_json(run_dir / "verdict.json")


def _weakness(
    *,
    category: str,
    summary: str,
    evidence: list[str],
    severity: str = "medium",
) -> dict[str, Any]:
    return {
        "category": category,
        "summary": summary,
        "evidence": evidence,
        "severity": severity,
    }


def mine_weaknesses(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    signals: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mine structured weaknesses from run artifacts."""
    spec = load_spec(root)
    signals = dict(signals or _load_json(run_dir / "improvement_signal.json") or {})
    snapshot = dict(snapshot or _load_json(run_dir / "improvement_snapshot.json") or {})
    stage = str(signals.get("stage") or snapshot.get("stage") or "")
    group = str(signals.get("group") or snapshot.get("group") or "")
    weaknesses: list[dict[str, Any]] = []

    sub_stop = _load_json(run_dir / "sub_stop.json")
    if sub_stop:
        weaknesses.append(
            _weakness(
                category="tool_artifact",
                summary=str(sub_stop.get("reason") or sub_stop.get("message") or "sub_stop halted graph"),
                evidence=[f"runs/{run_dir.name}/sub_stop.json"],
                severity="high",
            )
        )

    if int(signals.get("env_fail_steps") or 0) >= 2:
        weaknesses.append(
            _weakness(
                category="env_loop",
                summary="Repeated environment failures before gate success",
                evidence=[f"env_fail_steps={signals.get('env_fail_steps')}"],
            )
        )

    if signals.get("stalemate"):
        pattern = str(signals.get("stalemate_pattern") or "")
        cat = "stalemate_oscillation" if pattern == "OSCILLATION" else "stalemate_spin"
        weaknesses.append(
            _weakness(
                category=cat,
                summary=f"Loop guard stalemate ({pattern or 'unknown'})",
                evidence=[f"stalemate_pattern={pattern}"],
            )
        )

    verdict = _find_verdict(run_dir, group)
    if verdict:
        info_gap = verdict.get("info_gap") or verdict.get("INFO_GAP")
        if isinstance(info_gap, dict) and info_gap.get("fields"):
            weaknesses.append(
                _weakness(
                    category="info_gap",
                    summary="Verdict reports missing intake fields",
                    evidence=[str(info_gap.get("fields"))],
                )
            )
        if str(verdict.get("verdict") or "").upper() == "FAIL":
            weaknesses.append(
                _weakness(
                    category="verification_gap",
                    summary=str(verdict.get("summary") or "Gate verdict FAIL"),
                    evidence=[f"runs/{run_dir.name}/verdict_{group or '*'}.json"],
                )
            )

    if signals.get("parity_ok") is False:
        weaknesses.append(
            _weakness(
                category="parity_block",
                summary="Python vs LLM parity mismatch",
                evidence=["parity_ok=false"],
            )
        )

    if int(signals.get("llm_fix_rounds") or 0) >= 3 and str(signals.get("verdict")) != "PASS":
        weaknesses.append(
            _weakness(
                category="llm_inefficiency",
                summary="Multiple LLM fix rounds without PASS",
                evidence=[f"llm_fix_rounds={signals.get('llm_fix_rounds')}"],
            )
        )

    if signals.get("promoted") is False and str(signals.get("verdict")) == "PASS":
        weaknesses.append(
            _weakness(
                category="promote_block",
                summary="PASS without promote_outcome.promoted",
                evidence=["promoted=false"],
            )
        )

    trace = _read_graph_trace(run_dir)
    validation_nodes = [r for r in trace if str(r.get("node", "")).startswith("validation")]
    if validation_nodes and str(signals.get("verdict")) != "PASS":
        weaknesses.append(
            _weakness(
                category="validation_stall",
                summary="Validation subgraph active without final PASS",
                evidence=[f"validation_nodes={len(validation_nodes)}"],
            )
        )

    return {
        "contract": "weakness_report_v1",
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "mined_at": datetime.now(timezone.utc).isoformat(),
        "weaknesses": weaknesses,
        "categories_allowed": list(spec.get("weakness_categories") or []),
    }


def write_weakness_report(run_dir: Path, report: dict[str, Any]) -> Path:
    path = run_dir / WEAKNESS_REPORT
    _write_json(path, report)
    return path


def load_weakness_report(run_dir: Path) -> dict[str, Any]:
    return _load_json(run_dir / WEAKNESS_REPORT) or {}


def _layer_for_weakness(category: str) -> str:
    mapping = {
        "env_loop": "node_guide",
        "tool_artifact": "skill",
        "verification_gap": "verification_md",
        "validation_stall": "node_guide",
        "info_gap": "skill",
        "stalemate_spin": "node_guide",
        "stalemate_oscillation": "node_guide",
        "llm_inefficiency": "node_guide",
        "parity_block": "graph_source",
        "promote_block": "skill",
    }
    return mapping.get(category, "skill")


def _suggested_action(category: str, stage: str, group: str) -> str:
    hints = {
        "env_loop": "Run diagnose_env → patch_bridge before next run_gate",
        "tool_artifact": "Inspect sub_stop.json and fix script/artifact contract",
        "info_gap": "Ask user for firmware/sim paths; set user_provided=true in intake",
        "verification_gap": f"Re-read CHECK.md for {stage}/{group} tier markers",
        "validation_stall": "Parse validation_items; avoid premature finalize",
        "stalemate_spin": "Review loop_guard signature; consider force_mode",
        "stalemate_oscillation": "Enter validation autonomy instead of rerun gate",
        "parity_block": "Re-run parity_check; sync ops/{stage}/{group}.py",
        "llm_inefficiency": "Raise trust threshold when golden runner exists",
        "promote_block": "Complete promote_outcome before reproduction scripts",
    }
    return hints.get(category, f"Address {category} for {stage}/{group}")


def propose_harness_edits(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    weakness_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build harness edit proposals (proposal-only; never auto-apply graph source)."""
    spec = load_spec(root)
    report = weakness_report or load_weakness_report(run_dir)
    layers = spec.get("harness_layers") or {}
    stage = str(report.get("stage") or "")
    group = str(report.get("group") or "")

    proposals: list[dict[str, Any]] = []
    for w in report.get("weaknesses") or []:
        if not isinstance(w, dict):
            continue
        cat = str(w.get("category") or "")
        layer = _layer_for_weakness(cat)
        layer_spec = layers.get(layer) or {}
        proposals.append(
            {
                "weakness_category": cat,
                "layer": layer,
                "target_globs": list(layer_spec.get("globs") or []),
                "summary": w.get("summary"),
                "suggested_action": _suggested_action(cat, stage, group),
                "auto_apply_allowed": layer not in NEVER_AUTO_APPLY_LAYERS,
                "approval": layer_spec.get("approval") or (
                    "human_required" if layer in NEVER_AUTO_APPLY_LAYERS else "pytest"
                ),
            }
        )

    payload = {
        "contract": "harness_proposal_v1",
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "proposed_at": datetime.now(timezone.utc).isoformat(),
        "proposals": proposals,
        "never_auto_apply_layers": sorted(NEVER_AUTO_APPLY_LAYERS),
    }
    _write_json(run_dir / HARNESS_PROPOSAL, payload)
    return payload


def _skill_patch_for_weakness(
    *,
    category: str,
    summary: str,
    stage: str,
    group: str,
    target: str,
) -> dict[str, Any]:
    action = _suggested_action(category, stage, group)
    section = "Rules" if category in ("info_gap", "promote_block", "tool_artifact") else "Commands"
    return {
        "target": target,
        "weakness_category": category,
        "patch_type": "append_section",
        "section": section,
        "content": f"- [{category}] {summary} → {action}",
        "approval": "human_or_pytest",
        "auto_apply": False,
    }


def propose_llm_skill_patches(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    weakness_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured SKILL.md patch proposals for LLM/human review (never auto-apply)."""
    spec = load_spec(root)
    llm_cfg = spec.get("llm_proposal") or {}
    max_patches = int(llm_cfg.get("max_patches_per_run") or 5)
    default_targets = list(llm_cfg.get("default_skill_targets") or [".grok/skills/self-harness/SKILL.md"])

    report = weakness_report or load_weakness_report(run_dir)
    stage = str(report.get("stage") or "")
    group = str(report.get("group") or "")

    patches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for w in report.get("weaknesses") or []:
        if not isinstance(w, dict):
            continue
        cat = str(w.get("category") or "")
        if cat in seen:
            continue
        seen.add(cat)
        target = default_targets[0] if default_targets else ".grok/skills/self-harness/SKILL.md"
        patches.append(
            _skill_patch_for_weakness(
                category=cat,
                summary=str(w.get("summary") or cat),
                stage=stage,
                group=group,
                target=target,
            )
        )
        if len(patches) >= max_patches:
            break

    payload = {
        "contract": "harness_proposal_llm_v1",
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "proposed_at": datetime.now(timezone.utc).isoformat(),
        "skill_targets": default_targets,
        "patches": patches,
        "never_auto_apply_layers": sorted(NEVER_AUTO_APPLY_LAYERS),
        "instruction": (
            "Apply patches only after pytest validation and human review. "
            "Never auto-apply graph_source or project SKILL without gate."
        ),
    }
    _write_json(run_dir / HARNESS_PROPOSAL_LLM, payload)
    return payload


def write_harness_llm_prompt(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    weakness_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured LLM prompt for richer SKILL patch content generation."""
    spec = load_spec(root)
    llm_cfg = spec.get("llm_proposal") or {}
    report = weakness_report or load_weakness_report(run_dir)
    stage = str(report.get("stage") or "")
    group = str(report.get("group") or "")
    targets = list(llm_cfg.get("default_skill_targets") or [".grok/skills/self-harness/SKILL.md"])

    weakness_lines = []
    for w in report.get("weaknesses") or []:
        if not isinstance(w, dict):
            continue
        cat = str(w.get("category") or "")
        weakness_lines.append(
            f"- [{cat}] {w.get('summary')} → {_suggested_action(cat, stage, group)}"
        )

    payload = {
        "contract": "harness_llm_prompt_v1",
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "skill_targets": targets,
        "weaknesses": weakness_lines,
        "instruction": (
            "Generate append_section patches for each weakness. "
            "Each patch must cite evidence paths from weakness_report. "
            "Never auto-apply graph_source; human_or_pytest approval required."
        ),
        "output_schema": {
            "patches": [
                {
                    "target": "path/to/SKILL.md",
                    "section": "Rules|Commands",
                    "content": "markdown bullet lines",
                    "weakness_category": "category",
                }
            ]
        },
        "context_artifacts": [
            str(run_dir / WEAKNESS_REPORT),
            str(run_dir / HARNESS_PROPOSAL),
            str(run_dir / HARNESS_PROPOSAL_LLM),
        ],
    }
    _write_json(run_dir / HARNESS_LLM_PROMPT, payload)
    return payload


def held_out_intake_replay(root: Path, project_dir: Path) -> dict[str, Any]:
    """Replay representative intake YAML tier checks (held-out from run artifacts)."""
    spec = load_spec(root)
    intake_cfg = spec.get("held_out_intake") or {}
    rel = str(
        intake_cfg.get("representative_yaml")
        or "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    )
    intake_path = project_dir / rel
    if not intake_path.is_file():
        return {
            "ok": False,
            "error": f"missing intake: {rel}",
            "intake_path": str(intake_path),
            "issues": [f"missing:{rel}"],
        }

    try:
        from ops.intake_resolve import validate_intake_tier_consistency

        raw = intake_path.read_text(encoding="utf-8")
        if yaml is not None:
            intake = yaml.safe_load(raw) or {}
        else:
            intake = json.loads(raw)
        issues = list(validate_intake_tier_consistency(intake))
    except Exception as exc:  # pragma: no cover
        issues = [f"intake_replay_error:{exc}"]

    ok = len(issues) == 0
    return {
        "ok": ok,
        "intake_path": str(intake_path.relative_to(project_dir)),
        "issues": issues,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_harness_proposal(root: Path, run_dir: Path) -> dict[str, Any]:
    """Run pytest gate for self-harness validation targets."""
    spec = load_spec(root)
    proposal_path = run_dir / HARNESS_PROPOSAL
    if not proposal_path.is_file():
        result = {"ok": False, "error": "missing harness_proposal.json"}
        _write_json(run_dir / HARNESS_VALIDATION, result)
        return result

    targets = list((spec.get("validation") or {}).get("pytest_targets") or ["tests/test_self_harness.py"])
    cmd = [sys.executable, "-m", "pytest", *targets, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    ok = proc.returncode == 0
    result = {
        "ok": ok,
        "pytest_passed": ok,
        "returncode": proc.returncode,
        "targets": targets,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(run_dir / HARNESS_VALIDATION, result)
    return result


def held_out_reverify(
    root: Path,
    run_dir: Path,
    *,
    project_dir: Path | None = None,
) -> dict[str, Any]:
    """Run held-out pytest + intake replay before promote (defense against overfit)."""
    spec = load_spec(root)
    validation = spec.get("validation") or {}
    targets = list(validation.get("held_out_pytest_targets") or ["tests/test_intake_resolve.py"])
    require_pass = bool(validation.get("require_held_out_pass", True))
    intake_cfg = spec.get("held_out_intake") or {}
    require_intake = bool(intake_cfg.get("require_pass", True))

    cmd = [sys.executable, "-m", "pytest", *targets, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    pytest_ok = proc.returncode == 0

    intake_result: dict[str, Any] = {"ok": True, "skipped": True}
    if project_dir is not None and require_intake:
        intake_result = held_out_intake_replay(root, project_dir)
        intake_result.pop("skipped", None)

    ok = pytest_ok and (intake_result.get("ok", True) or not require_intake)
    result = {
        "ok": ok,
        "pytest_passed": pytest_ok,
        "intake_replay": intake_result,
        "require_held_out_pass": require_pass,
        "promote_allowed": ok or not require_pass,
        "returncode": proc.returncode,
        "targets": targets,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(run_dir / HARNESS_HELD_OUT_VALIDATION, result)
    return result


def harness_status(project_dir: Path, run_dir: Path) -> dict[str, Any]:
    artifacts = {
        "weakness_report": (run_dir / WEAKNESS_REPORT).is_file(),
        "harness_proposal": (run_dir / HARNESS_PROPOSAL).is_file(),
        "harness_proposal_llm": (run_dir / HARNESS_PROPOSAL_LLM).is_file(),
        "harness_validation": (run_dir / HARNESS_VALIDATION).is_file(),
        "harness_held_out_validation": (run_dir / HARNESS_HELD_OUT_VALIDATION).is_file(),
        "harness_llm_prompt": (run_dir / HARNESS_LLM_PROMPT).is_file(),
        "llm_brief": (run_dir / "llm_brief.json").is_file(),
        "meta_collect_prompt": (run_dir / "meta_collect_prompt.json").is_file(),
        "improvement_signal": (run_dir / "improvement_signal.json").is_file(),
        "erl_heuristic": (project_dir / "knowledge" / "patterns" / f"{run_dir.name}.md").is_file(),
    }
    validation = _load_json(run_dir / HARNESS_VALIDATION) or {}
    held_out = _load_json(run_dir / HARNESS_HELD_OUT_VALIDATION) or {}
    return {
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "artifacts": artifacts,
        "validation_ok": validation.get("ok"),
        "held_out_ok": held_out.get("ok"),
        "promote_allowed": held_out.get("promote_allowed"),
        "weakness_count": len((load_weakness_report(run_dir).get("weaknesses") or [])),
    }


def update_patterns_index(
    project_dir: Path,
    *,
    run_id: str,
    tags: list[str],
    title: str,
) -> Path:
    index_path = project_dir / "knowledge" / "patterns" / "index.yaml"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index = load_yaml(index_path)
    entries = list(index.get("entries") or [])
    entries = [e for e in entries if not (isinstance(e, dict) and e.get("run_id") == run_id)]
    entries.append(
        {
            "run_id": run_id,
            "title": title,
            "tags": tags,
            "path": f"knowledge/patterns/{run_id}.md",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    index["entries"] = entries[-50:]
    save_yaml(index_path, index)
    return index_path


def _tag_score(heuristic_tags: list[str], *, stage: str, group: str, error_kind: str) -> int:
    score = 0
    want = [
        f"#stage/{stage}" if stage else "",
        f"#group/{group}" if group else "",
        f"#error_kind/{error_kind}" if error_kind else "",
    ]
    for tag in heuristic_tags:
        if tag in want:
            score += 3
        elif tag.startswith("#project/"):
            score += 1
    return score


def retrieve_erl_context(
    project_dir: Path,
    *,
    stage: str = "",
    group: str = "",
    error_kind: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Tag-ranked ERL heuristic retrieval for next-run brief."""
    spec_root = _repo_root(project_dir)
    spec = load_spec(spec_root)
    erl_cfg = spec.get("erl") or {}
    max_items = int(erl_cfg.get("max_heuristics_per_retrieval") or limit)
    limit = min(limit, max_items)

    patterns_dir = project_dir / "knowledge" / "patterns"
    if not patterns_dir.is_dir():
        return []

    ranked: list[tuple[int, str, Path]] = []
    for path in sorted(patterns_dir.glob("*.md")):
        if path.name.startswith("index."):
            continue
        text = path.read_text(encoding="utf-8")
        tags = re.findall(r"^tags:\s*(.+)$", text, re.M)
        tag_list = tags[0].split() if tags else []
        score = _tag_score(tag_list, stage=stage, group=group, error_kind=error_kind)
        ranked.append((score, path.stem, path))

    ranked.sort(key=lambda x: (-x[0], x[1]))
    out: list[dict[str, Any]] = []
    for score, run_id, path in ranked[: max(1, limit)]:
        out.append(
            {
                "run_id": run_id,
                "score": score,
                "path": str(path.relative_to(project_dir)),
                "excerpt": path.read_text(encoding="utf-8")[:800],
            }
        )
    return out