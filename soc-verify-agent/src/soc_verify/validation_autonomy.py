"""SoC validation autonomy — per-item goals, LLM judgment, repro/exclude/continue."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.bridge_env import apply_profile_to_environ
from soc_verify.execution_log import append_execution_log
from soc_verify.models import load_yaml, save_yaml

SPEC_NAME = "validation_autonomy_spec.yaml"

_TIER_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|",
    re.MULTILINE,
)
_CHECKLIST_RE = re.compile(
    r"Checklist:\s*(\d+)\s+passed\s*/\s*(\d+)\s+failed",
    re.IGNORECASE,
)
_TIER_MARKER_FAIL_RE = re.compile(
    r"\[(?:FAIL|ERROR)\]|checklist failed count=|cmd exit=(?!0\b)",
    re.IGNORECASE,
)


def load_spec(root: Path) -> dict[str, Any]:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return load_yaml(p) or {}


def validation_state_path(project_dir: Path) -> Path:
    return project_dir / "meta" / "validation_state.yaml"


def load_validation_state(project_dir: Path) -> dict[str, Any]:
    path = validation_state_path(project_dir)
    if not path.is_file():
        return {"contract": "validation_state_v1", "excluded_items": [], "pending_repro": []}
    data = load_yaml(path)
    if not isinstance(data, dict):
        return {"contract": "validation_state_v1", "excluded_items": [], "pending_repro": []}
    data.setdefault("excluded_items", [])
    data.setdefault("pending_repro", [])
    return data


def save_validation_state(project_dir: Path, state: dict[str, Any]) -> Path:
    path = validation_state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["contract"] = "validation_state_v1"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_yaml(path, state)
    return path


def _check_md_path(project_dir: Path, stage: str, group: str) -> Path:
    return project_dir / "verification" / stage / group / "CHECK.md"


def _parse_tiers_from_check(check_text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for m in _TIER_ROW_RE.finditer(check_text):
        tier_id = m.group(1).strip()
        if tier_id.lower() in ("tier", "------"):
            continue
        items.append(
            {
                "item_id": tier_id,
                "label": tier_id,
                "kind": "tier",
                "goal": "PASS markers per CHECK.md",
                "actual": "",
                "status": "unknown",
            }
        )
    return items


def _scan_run_logs(run_dir: Path, group: str) -> str:
    chunks: list[str] = []
    if not run_dir.is_dir():
        return ""
    for path in sorted(run_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix not in (".log", ".out", ".txt") and group not in path.name:
            continue
        if path.suffix in (".log", ".out") or group in path.name:
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return "\n".join(chunks)


def _apply_log_signals(items: list[dict[str, Any]], log_text: str) -> list[dict[str, Any]]:
    if not log_text.strip():
        return items

    checklist_m = _CHECKLIST_RE.search(log_text)
    global_checklist_fail = int(checklist_m.group(2)) if checklist_m else None

    for item in items:
        tier = str(item.get("item_id", ""))
        tier_present = tier and tier in log_text
        if not tier_present and len(items) > 1:
            continue
        segment = log_text if not tier_present else _extract_tier_segment(log_text, tier)
        fails = _TIER_MARKER_FAIL_RE.search(segment) or (
            global_checklist_fail and global_checklist_fail > 0
        )
        if checklist_m and tier_present:
            local = _CHECKLIST_RE.search(segment)
            if local:
                item["actual"] = f"checklist {local.group(1)}/{local.group(2)} failed"
                item["status"] = "fail" if int(local.group(2)) > 0 else "pass"
                continue
        if fails:
            item["actual"] = item.get("actual") or "log markers indicate failure"
            item["status"] = "fail"
        elif tier_present or len(items) == 1:
            if item.get("status") == "unknown":
                item["status"] = "pass" if not fails else "fail"

    if not items and global_checklist_fail is not None:
        items.append(
            {
                "item_id": "checklist_aggregate",
                "label": "checklist",
                "kind": "checklist",
                "goal": "0 failed",
                "actual": f"{checklist_m.group(1)} passed / {checklist_m.group(2)} failed",
                "status": "fail" if global_checklist_fail > 0 else "pass",
            }
        )
    return items


def _extract_tier_segment(log_text: str, tier: str) -> str:
    idx = log_text.find(tier)
    if idx < 0:
        return log_text
    return log_text[max(0, idx - 500) : idx + 4000]


def collect_validation_items(
    project_dir: Path,
    *,
    stage: str,
    group: str,
    run_dir: Path,
) -> dict[str, Any]:
    """Mechanical extraction of validation items (SoC goal-oriented, not coverage)."""
    check_path = _check_md_path(project_dir, stage, group)
    check_text = check_path.read_text(encoding="utf-8") if check_path.is_file() else ""
    items = _parse_tiers_from_check(check_text)

    if not items:
        items = [
            {
                "item_id": f"{stage}_{group}",
                "label": f"{stage}/{group}",
                "kind": "gate",
                "goal": "verdict PASS per CHECK.md",
                "actual": "",
                "status": "unknown",
            }
        ]

    verdict_path = run_dir / f"verdict_{group}.json"
    verdict_status = ""
    if verdict_path.is_file():
        try:
            vd = json.loads(verdict_path.read_text(encoding="utf-8"))
            verdict_status = str(vd.get("status", vd.get("verdict", "")))
            for item in items:
                if verdict_status and verdict_status != "PASS":
                    item.setdefault("actual", f"verdict={verdict_status}")
                    if item.get("status") == "unknown":
                        item["status"] = "fail"
        except json.JSONDecodeError:
            pass

    log_text = _scan_run_logs(run_dir, group)
    items = _apply_log_signals(items, log_text)

    failing = [i for i in items if i.get("status") == "fail"]
    payload = {
        "contract": "validation_items_v1",
        "paradigm": "soc_validation",
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "check_md": str(check_path.relative_to(project_dir.parent.parent)) if check_path.is_file() else "",
        "verdict": verdict_status,
        "items": items,
        "failing_count": len(failing),
        "needs_judgment": len(failing) > 0 or verdict_status not in ("", "PASS"),
    }
    return payload


def write_validation_items(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / "validation_items.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def build_validation_judge_prompt(
    *,
    project_dir: Path,
    stage: str,
    group: str,
    run_id: str,
    items_payload: dict[str, Any],
) -> dict[str, Any]:
    check_path = _check_md_path(project_dir, stage, group)
    respond_path = project_dir / "verification" / stage / group / "RESPOND.md"
    prior = load_validation_state(project_dir)
    return {
        "contract": "validation_judge_prompt_v1",
        "task": "soc_validation_judge",
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "run_id": run_id,
        "paradigm": "soc_validation_not_ip_coverage",
        "validation_items": items_payload,
        "prior_state": {
            "excluded_items": prior.get("excluded_items") or [],
            "pending_repro": prior.get("pending_repro") or [],
        },
        "reads": [
            str(check_path.relative_to(project_dir.parent.parent)) if check_path.is_file() else "",
            str(respond_path.relative_to(project_dir.parent.parent)) if respond_path.is_file() else "",
            f"projects/{project_dir.name}/runs/{run_id}/validation_items.json",
        ],
        "required_output": f"projects/{project_dir.name}/runs/{run_id}/validation_judgment.json",
        "actions": ["reproduce", "narrow_cause", "repro_script", "exclude", "continue_rest"],
        "sequence_actions": ["halt", "retry_gate", "continue_remaining", "partial_accept"],
    }


def _mechanical_judgment(items_payload: dict[str, Any]) -> dict[str, Any]:
    """Stub/fallback when LLM has not written judgment yet."""
    items_out: list[dict[str, Any]] = []
    for raw in items_payload.get("items") or []:
        if raw.get("status") != "fail":
            continue
        iid = str(raw.get("item_id", "item"))
        items_out.append(
            {
                "item_id": iid,
                "status": "fail",
                "action": "narrow_cause",
                "user_summary_ko": (
                    f"「{iid}」 goal 미달 — log·CHECK.md 확인. "
                    f"actual: {raw.get('actual', '—')}"
                ),
                "narrow_hints": [
                    f"runs/*/ {iid} 구간 log",
                    f"verification/{items_payload.get('stage')}/{items_payload.get('group')}/RESPOND.md",
                ],
                "repro_script": f"scripts/repro_{iid}.sh",
                "exclude_reason": "",
            }
        )
    if not items_out:
        return {
            "contract": "validation_judgment_v1",
            "source": "mechanical",
            "verdict_summary_ko": "failing item 없음",
            "sequence_action": "halt",
            "items": [],
        }
    return {
        "contract": "validation_judgment_v1",
        "source": "mechanical",
        "verdict_summary_ko": f"실패 item {len(items_out)}개 — 원인 좁히기 후 gate 재시도",
        "sequence_action": "retry_gate",
        "items": items_out,
    }


def load_validation_judgment(run_dir: Path, items_payload: dict[str, Any]) -> dict[str, Any]:
    path = run_dir / "validation_judgment.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("contract") == "validation_judgment_v1":
                return data
        except json.JSONDecodeError:
            pass
    mechanical = _mechanical_judgment(items_payload)
    if run_dir.parent.name == "runs":
        root = run_dir.parent.parent.parent.parent
    else:
        root = Path.cwd()
    spec = load_spec(root)
    fb = (spec.get("mechanical_fallback") or {}).get("sequence_action")
    if fb and mechanical.get("source") == "mechanical" and mechanical.get("items"):
        mechanical["sequence_action"] = str(fb)
    return mechanical


def apply_validation_judgment(
    project_dir: Path,
    run_dir: Path,
    judgment: dict[str, Any],
    *,
    stage: str,
    group: str,
) -> dict[str, Any]:
    """Apply LLM/mechanical plan — narrow.md, excludes, repro prompts."""
    state = load_validation_state(project_dir)
    excluded = list(state.get("excluded_items") or [])
    pending_repro = list(state.get("pending_repro") or [])
    narrow_lines = [
        f"# Validation narrow — {stage}/{group}",
        "",
        judgment.get("verdict_summary_ko", ""),
        "",
        f"sequence_action: **{judgment.get('sequence_action', 'halt')}**",
        "",
    ]
    repro_prompts: list[str] = []
    applied: list[dict[str, Any]] = []

    for entry in judgment.get("items") or []:
        if not isinstance(entry, dict):
            continue
        iid = str(entry.get("item_id", ""))
        action = str(entry.get("action", "narrow_cause"))
        applied.append({"item_id": iid, "action": action})

        narrow_lines.append(f"## {iid}")
        narrow_lines.append(entry.get("user_summary_ko", ""))
        for hint in entry.get("narrow_hints") or []:
            narrow_lines.append(f"- {hint}")
        narrow_lines.append("")

        if action == "exclude":
            excluded.append(
                {
                    "item_id": iid,
                    "stage": stage,
                    "group": group,
                    "reason": entry.get("exclude_reason", "llm_exclude"),
                }
            )
        elif action in ("reproduce", "repro_script"):
            script = str(entry.get("repro_script") or f"scripts/repro_{iid}.sh")
            repro_prompts.append(script)
            pending_repro.append(
                {
                    "item_id": iid,
                    "stage": stage,
                    "group": group,
                    "script": script,
                    "run_id": run_dir.name,
                    "prompt": f"runs/{run_dir.name}/validation_item_repro_{iid}.json",
                }
            )
            prompt_path = run_dir / f"validation_item_repro_{iid}.json"
            prompt_path.write_text(
                json.dumps(
                    {
                        "contract": "validation_item_repro_v1",
                        "item_id": iid,
                        "stage": stage,
                        "group": group,
                        "script": script,
                        "instruction": (
                            f"Write minimal bash repro for item {iid} only — "
                            "no full regression, no gate CLI on orchestrator."
                        ),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    narrow_path = run_dir / "validation_narrow.md"
    narrow_path.write_text("\n".join(narrow_lines).strip() + "\n", encoding="utf-8")

    state["excluded_items"] = excluded
    state["pending_repro"] = pending_repro
    state["last_sequence_action"] = judgment.get("sequence_action")
    save_validation_state(project_dir, state)

    judgment_path = run_dir / "validation_judgment.json"
    judgment_path.write_text(json.dumps(judgment, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "narrow_md": str(narrow_path.relative_to(project_dir.parent.parent)),
        "applied": applied,
        "repro_prompts": repro_prompts,
        "sequence_action": judgment.get("sequence_action"),
        "excluded_count": len(excluded),
        "pending_repro_count": len(pending_repro),
    }


def run_pending_repro(
    project_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    group: str,
    run_id: str,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Execute item-level repro scripts for current run — no full gate CLI."""
    state = load_validation_state(project_dir)
    pending = [
        p
        for p in (state.get("pending_repro") or [])
        if isinstance(p, dict)
        and str(p.get("run_id")) == run_id
        and str(p.get("stage")) == stage
        and str(p.get("group")) == group
    ]
    results: list[dict[str, Any]] = []
    for entry in pending:
        item_id = str(entry.get("item_id", ""))
        script_rel = str(entry.get("script") or f"scripts/repro_{item_id}.sh")
        script_path = project_dir / script_rel
        if not script_path.is_file():
            results.append(
                {
                    "item_id": item_id,
                    "status": "missing_script",
                    "script": script_rel,
                    "exit_code": None,
                }
            )
            continue
        argv = [
            "bash",
            str(script_path),
            "--project",
            str(project_dir),
            "--run-dir",
            str(run_dir),
        ]
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            cwd=str(project_dir),
            env=apply_profile_to_environ(project_dir),
        )
        log_path = run_dir / f"repro_{item_id}.log"
        log_path.write_text(
            (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or ""),
            encoding="utf-8",
        )
        append_execution_log(
            run_dir,
            command=argv,
            node="run_pending_repro",
            exit_code=proc.returncode,
            artifact_paths=[str(log_path)],
        )
        results.append(
            {
                "item_id": item_id,
                "status": "pass" if proc.returncode == 0 else "fail",
                "exit_code": proc.returncode,
                "script": script_rel,
                "log": f"runs/{run_id}/repro_{item_id}.log",
            }
        )

    payload: dict[str, Any] = {
        "contract": "validation_repro_results_v1",
        "run_id": run_id,
        "stage": stage,
        "group": group,
        "pending_count": len(pending),
        "executed_count": sum(1 for r in results if r["status"] in ("pass", "fail")),
        "results": results,
    }
    out_path = run_dir / "validation_repro_results.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def is_group_excluded(project_dir: Path, stage: str, group: str) -> bool:
    state = load_validation_state(project_dir)
    for ex in state.get("excluded_items") or []:
        if not isinstance(ex, dict):
            continue
        if str(ex.get("stage")) == stage and str(ex.get("group")) == group and not ex.get("item_id"):
            return True
    return False


def filter_work_queue_by_validation(root: Path, queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Orchestrator: skip fully excluded gates; item-level excludes stay in-gate."""
    out: list[dict[str, Any]] = []
    config_projects = root / "projects"
    for w in queue:
        if w.get("kind") != "verify":
            out.append(w)
            continue
        pid = str(w.get("project_id", ""))
        stage = str(w.get("stage", ""))
        group = str(w.get("group", ""))
        project_dir = config_projects / pid
        if project_dir.is_dir() and is_group_excluded(project_dir, stage, group):
            continue
        out.append(w)
    return out