"""Load user config.json — only user-defined workspace settings."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UserConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def workspace_id(self) -> str:
        return str(self.raw.get("workspace_id", "default"))

    @property
    def projects_root(self) -> Path:
        rel = (self.raw.get("paths") or {}).get("projects_root", "./projects")
        return (self.path.parent / rel).resolve()

    @property
    def tag_refresh_days(self) -> int:
        return int((self.raw.get("schedules") or {}).get("tag_refresh_days", 4))

    @property
    def project_search_days(self) -> int:
        return int((self.raw.get("schedules") or {}).get("project_search_days", 7))

    @property
    def project_intake_days(self) -> int:
        return int((self.raw.get("schedules") or {}).get("project_intake_days", 30))

    @property
    def confluence_hints(self) -> dict[str, Any]:
        return (self.raw.get("confluence") or {}).get("hints") or {}

    @property
    def field_map(self) -> dict[str, str]:
        return self.confluence_hints.get("field_map") or {}

    @property
    def git_clone_root(self) -> str:
        return str((self.raw.get("git") or {}).get("clone_root", "/work/repos"))

    @property
    def jira(self) -> dict[str, Any]:
        return self.raw.get("jira") or {}

    @property
    def environment(self) -> dict[str, Any]:
        return self.raw.get("environment") or {}

    @property
    def overrides(self) -> dict[str, Any]:
        return self.raw.get("overrides") or {}


def load_user_config(root: Path | None = None) -> UserConfig:
    root = root or Path.cwd()
    for candidate in [root / "config.json", root.parent / "config.json"]:
        if candidate.is_file():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            return UserConfig(raw=data, path=candidate)
    raise FileNotFoundError("config.json not found — copy config.example.json")


def load_policies(root: Path | None = None) -> dict[str, Any]:
    import yaml

    root = root or Path.cwd()
    path = root / "registry" / "policies.yaml"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "registry" / "policies.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}