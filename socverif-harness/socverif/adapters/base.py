"""Base adapter interface — optional plugins; generic adapter is always the fallback."""
# goal_build_id = 12

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TierSpec:
    tier: int
    name: str
    compile_cmd: str = ""
    sim_cmd: str = ""
    cwd: str = "."
    log_glob: str = "sim_logs/*.log"
    pass_fail: dict[str, Any] = field(default_factory=dict)
    timeout_sec: int = 600


class EnvironmentAdapter(ABC):
    id: str = "generic"
    name: str = "Generic"

    @abstractmethod
    def detect(self, root: Path, context: dict[str, Any]) -> bool:
        """Return True if this adapter applies to the project."""

    @abstractmethod
    def enrich_manifest(self, root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
        """Augment discovered manifest with adapter-specific tiers and pass/fail."""

    def build_tiers(self, root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        return manifest.get("tiers", [])