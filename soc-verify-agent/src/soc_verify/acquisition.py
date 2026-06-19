"""Acquisition dates and refresh scheduling for search, intake, tag watch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from soc_verify.config import UserConfig, load_user_config
from soc_verify.models import load_yaml
from soc_verify.tag_cache import should_refresh_tag

AcquisitionKind = Literal[
    "project_search",
    "project_intake",
    "knowledge_collect",
    "state_sync",
    "tag_watch",
]


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def next_refresh(fetched: date, interval_days: int) -> date:
    return fetched + timedelta(days=interval_days)


def _block_due(
    block: dict[str, Any] | None,
    *,
    interval_days: int,
    today: date,
) -> tuple[bool, date | None, date | None]:
    """Return (is_due, fetched_at, next_refresh). Missing fetched_at → due."""
    if not block:
        return True, None, None

    fetched = parse_date(block.get("fetched_at"))
    policy = block.get("refresh_policy") or {}
    next_at = parse_date(policy.get("next_refresh"))

    if fetched is None:
        return True, None, next_at

    if next_at is None:
        interval = int(policy.get("interval_days") or interval_days)
        next_at = next_refresh(fetched, interval)

    return today >= next_at, fetched, next_at


def should_refresh_project_search(
    registry: dict[str, Any],
    config: UserConfig,
    today: date | None = None,
) -> bool:
    today = today or date.today()
    block = (registry.get("acquisition") or {}).get("project_search") or {}
    days = int((config.raw.get("schedules") or {}).get("project_search_days", 7))
    due, _, _ = _block_due(block, interval_days=days, today=today)
    return due


def should_refresh_intake(
    discovered: dict[str, Any],
    config: UserConfig,
    today: date | None = None,
) -> bool:
    today = today or date.today()
    block = discovered.get("intake") or {}
    if not block.get("fetched_at") and discovered.get("last_intake"):
        block = {**block, "fetched_at": discovered["last_intake"]}
    days = int((config.raw.get("schedules") or {}).get("project_intake_days", 30))
    due, _, _ = _block_due(block, interval_days=days, today=today)
    return due


def should_refresh_knowledge_collect(
    sync: dict[str, Any],
    config: UserConfig,
    today: date | None = None,
) -> bool:
    today = today or date.today()
    days = config.knowledge_collect_days
    due, _, _ = _block_due(sync if sync.get("fetched_at") else None, interval_days=days, today=today)
    if not sync.get("fetched_at"):
        return True
    return due


def should_refresh_state_sync(
    state: dict[str, Any],
    config: UserConfig,
    today: date | None = None,
) -> bool:
    today = today or date.today()
    block = state.get("sync") or {}
    if not block.get("fetched_at") and state.get("as_of"):
        block = {**block, "fetched_at": state["as_of"]}
    days = int((config.raw.get("schedules") or {}).get("project_intake_days", 30))
    due, _, _ = _block_due(block, interval_days=days, today=today)
    return due


@dataclass
class AcquisitionStatus:
    kind: AcquisitionKind
    label_ko: str
    fetched_at: str | None
    next_refresh: str | None
    due: bool
    stored_in: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label_ko": self.label_ko,
            "fetched_at": self.fetched_at,
            "next_refresh": self.next_refresh,
            "due": self.due,
            "stored_in": self.stored_in,
        }


def project_acquisition_status(
    project_dir: Path,
    config: UserConfig | None = None,
    today: date | None = None,
) -> list[AcquisitionStatus]:
    today = today or date.today()
    if config is None:
        root = project_dir.parent.parent
        try:
            config = load_user_config(root)
        except FileNotFoundError:
            from soc_verify.config import UserConfig as UC

            config = UC(raw={"schedules": {}}, path=root / "config.json")

    discovered = load_yaml(project_dir / "discovered.yaml")
    state = load_yaml(project_dir / "state.yaml")
    cache = load_yaml(project_dir / "cache.yaml")

    intake_days = int((config.raw.get("schedules") or {}).get("project_intake_days", 30))
    knowledge_days = config.knowledge_collect_days
    tag_days = config.tag_refresh_days

    intake_block = discovered.get("intake") or {}
    if not intake_block.get("fetched_at") and discovered.get("last_intake"):
        intake_block = {**intake_block, "fetched_at": discovered["last_intake"]}
    intake_due, intake_fetched, intake_next = _block_due(
        intake_block, interval_days=intake_days, today=today
    )

    sync_block = state.get("sync") or {}
    if not sync_block.get("fetched_at") and state.get("as_of"):
        sync_block = {**sync_block, "fetched_at": state["as_of"]}
    sync_due, sync_fetched, sync_next = _block_due(
        sync_block, interval_days=intake_days, today=today
    )

    from soc_verify.knowledge_ops import load_knowledge_sync

    knowledge_sync = load_knowledge_sync(project_dir)
    know_due, know_fetched, know_next = _block_due(
        knowledge_sync if knowledge_sync.get("fetched_at") else None,
        interval_days=knowledge_days,
        today=today,
    )
    if not knowledge_sync.get("fetched_at"):
        know_due = True

    tag_block = cache.get("tag") or {}
    tag_due = should_refresh_tag(cache, today)
    tag_fetched = parse_date(tag_block.get("fetched_at"))
    tag_next = parse_date((tag_block.get("refresh_policy") or {}).get("next_refresh"))
    if tag_fetched and tag_next is None:
        tag_next = next_refresh(tag_fetched, tag_days)

    pid = project_dir.name
    return [
        AcquisitionStatus(
            kind="project_intake",
            label_ko="과제 정보 갱신",
            fetched_at=intake_fetched.isoformat() if intake_fetched else None,
            next_refresh=intake_next.isoformat() if intake_next else None,
            due=intake_due,
            stored_in=f"projects/{pid}/discovered.yaml",
        ),
        AcquisitionStatus(
            kind="knowledge_collect",
            label_ko="지식 수집 (Confluence/wiki/md)",
            fetched_at=know_fetched.isoformat() if know_fetched else None,
            next_refresh=know_next.isoformat() if know_next else None,
            due=know_due,
            stored_in=f"projects/{pid}/intake/knowledge_sync.yaml",
        ),
        AcquisitionStatus(
            kind="state_sync",
            label_ko="과제 상태 동기화",
            fetched_at=sync_fetched.isoformat() if sync_fetched else None,
            next_refresh=sync_next.isoformat() if sync_next else None,
            due=sync_due,
            stored_in=f"projects/{pid}/state.yaml",
        ),
        AcquisitionStatus(
            kind="tag_watch",
            label_ko="태그 감시·갱신",
            fetched_at=tag_fetched.isoformat() if tag_fetched else None,
            next_refresh=tag_next.isoformat() if tag_next else None,
            due=tag_due,
            stored_in=f"projects/{pid}/cache.yaml",
        ),
    ]


def workspace_acquisition_status(
    root: Path,
    config: UserConfig | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    root = root.resolve()
    if config is None:
        config = load_user_config(root)

    registry_path = root / "registry" / "active_projects.yaml"
    registry = load_yaml(registry_path)
    search_days = int((config.raw.get("schedules") or {}).get("project_search_days", 7))
    search_block = (registry.get("acquisition") or {}).get("project_search") or {}
    search_due, search_fetched, search_next = _block_due(
        search_block, interval_days=search_days, today=today
    )

    projects_root = config.projects_root
    project_ids = sorted(
        d.name for d in projects_root.iterdir() if d.is_dir() and (d / "discovered.yaml").is_file()
    )

    per_project: dict[str, list[dict[str, Any]]] = {}
    any_due: list[str] = []
    for pid in project_ids:
        statuses = project_acquisition_status(projects_root / pid, config, today)
        per_project[pid] = [s.to_dict() for s in statuses]
        if any(s.due for s in statuses):
            any_due.append(pid)

    return {
        "as_of": today.isoformat(),
        "workspace_id": config.workspace_id,
        "project_search": {
            "due": search_due,
            "fetched_at": search_fetched.isoformat() if search_fetched else None,
            "next_refresh": search_next.isoformat() if search_next else None,
            "stored_in": "registry/active_projects.yaml",
        },
        "projects": per_project,
        "projects_with_due_work": any_due,
    }


def stamp_refresh_policy(
    fetched_at: date,
    interval_days: int,
) -> dict[str, Any]:
    return {
        "fetched_at": fetched_at.isoformat(),
        "refresh_policy": {
            "interval_days": interval_days,
            "next_refresh": next_refresh(fetched_at, interval_days).isoformat(),
        },
    }