"""Schedule & event triggers for milestones, pipeline steps, meta innovation loop."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml


CRON_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$"
)


@dataclass
class TriggerDue:
    target_id: str
    target_kind: str
    reason: str
    trigger_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "reason": self.reason,
            "trigger_type": self.trigger_type,
        }


def _schedule_path(project_dir: Path) -> Path:
    return project_dir / "meta" / "schedule.yaml"


def load_project_schedule(project_dir: Path) -> dict[str, Any]:
    path = _schedule_path(project_dir)
    if not path.is_file():
        return {"contract": "project_schedule_v1", "milestones": {}, "pipelines": {}, "meta_innovation_loop": {}}
    data = load_yaml(path)
    return data if isinstance(data, dict) else {}


def save_project_schedule(project_dir: Path, schedule: dict[str, Any]) -> Path:
    path = _schedule_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    schedule["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_yaml(path, schedule)
    return path


def _cron_field_matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return value % step == 0
    if "," in field:
        return value in [int(x) for x in field.split(",")]
    if "-" in field:
        lo, hi = field.split("-", 1)
        return int(lo) <= value <= int(hi)
    return int(field) == value


def cron_matches(cron: str, dt: datetime | None = None) -> bool:
    """Minimal 5-field cron matcher (minute hour dom month dow)."""
    m = CRON_RE.match(cron.strip())
    if not m:
        return False
    dt = dt or datetime.now(timezone.utc)
    minute, hour, dom, month, dow = m.groups()
    return (
        _cron_field_matches(minute, dt.minute)
        and _cron_field_matches(hour, dt.hour)
        and _cron_field_matches(dom, dt.day)
        and _cron_field_matches(month, dt.month)
        and _cron_field_matches(dow, dt.weekday())
    )


def check_event_triggers(
    *,
    events: list[str],
    refresh_spec: dict[str, Any],
) -> list[str]:
    due: list[str] = []
    configured = list(refresh_spec.get("events") or [])
    for ev in configured:
        if ev in events:
            due.append(ev)
    return due


def is_refresh_due(
    refresh_spec: dict[str, Any],
    *,
    last_run: str = "",
    today: date | None = None,
    pending_events: list[str] | None = None,
) -> tuple[bool, str]:
    pending_events = pending_events or []
    cron = str(refresh_spec.get("cron", ""))
    if cron and cron_matches(cron):
        return True, "cron"
    ev_hits = check_event_triggers(events=pending_events, refresh_spec=refresh_spec)
    if ev_hits:
        return True, f"event:{ev_hits[0]}"
    interval_days = int(refresh_spec.get("interval_days", 0))
    if interval_days and last_run:
        try:
            last = date.fromisoformat(last_run[:10])
            today = today or date.today()
            if (today - last).days >= interval_days:
                return True, "interval"
        except ValueError:
            pass
    return False, ""


def collect_due_triggers(
    project_dir: Path,
    *,
    pending_events: list[str] | None = None,
    root: Path | None = None,
) -> list[TriggerDue]:
    """Check project schedule + pipeline spec refresh for due work."""
    from soc_verify.milestone_pipeline import list_pipelines

    pending_events = pending_events or []
    due: list[TriggerDue] = []
    schedule = load_project_schedule(project_dir)
    today = date.today().isoformat()

    mil_sched = schedule.get("meta_innovation_loop") or {}
    last_mil = str(mil_sched.get("last_run", ""))
    mil_refresh = mil_sched.get("refresh") or {"cron": "0 3 * * 0"}
    ok, reason = is_refresh_due(mil_refresh, last_run=last_mil, pending_events=pending_events)
    if ok or mil_sched.get("run_now"):
        due.append(TriggerDue("meta_innovation_loop", "graph", reason or "manual", "meta_innovation"))

    if root:
        for pl in list_pipelines(root):
            pid = str(pl.get("id", ""))
            nodes = pl.get("nodes") or {}
            for nid, node in nodes.items():
                if not isinstance(node, dict):
                    continue
                refresh = node.get("refresh") or {}
                step_sched = (schedule.get("pipelines") or {}).get(pid, {}).get("steps", {}).get(nid, {})
                last = str(step_sched.get("last_run", ""))
                ok2, reason2 = is_refresh_due(refresh, last_run=last, pending_events=pending_events)
                if ok2:
                    due.append(
                        TriggerDue(
                            f"{pid}/{nid}",
                            "pipeline_step",
                            reason2,
                            str(node.get("graph", "verify_group")),
                        )
                    )
    return due


def mark_trigger_run(project_dir: Path, target_kind: str, target_id: str) -> None:
    schedule = load_project_schedule(project_dir)
    today = date.today().isoformat()
    if target_kind == "meta_innovation":
        schedule.setdefault("meta_innovation_loop", {})["last_run"] = today
        schedule["meta_innovation_loop"].pop("run_now", None)
    elif target_kind == "pipeline_step":
        pid, _, nid = target_id.partition("/")
        schedule.setdefault("pipelines", {}).setdefault(pid, {}).setdefault("steps", {}).setdefault(nid, {})[
            "last_run"
        ] = today
    save_project_schedule(project_dir, schedule)


def request_immediate(project_dir: Path, *, meta_innovation: bool = True) -> Path:
    schedule = load_project_schedule(project_dir)
    if meta_innovation:
        schedule.setdefault("meta_innovation_loop", {})["run_now"] = True
    return save_project_schedule(project_dir, schedule)