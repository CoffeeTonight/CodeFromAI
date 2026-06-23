"""Shared data models and YAML I/O."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from soc_verify.file_lock import file_lock


RunnerMode = Literal["python", "llm"]
ScriptStatus = Literal["spawned", "draft", "evaluated", "reliable", "canonical", "deprecated"]
VerdictStatus = Literal["PASS", "FAIL", "BLOCKED", "INFO_GAP"]
PromoteDecision = Literal["approve", "defer", "reject"]


@dataclass
class InfoGapError(Exception):
    """Missing information that only a human can provide."""

    message: str
    field: str = ""

    def __str__(self) -> str:
        return self.message


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with file_lock(path, exclusive=False):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with file_lock(path, exclusive=True):
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        tmp.replace(path)


@dataclass
class SubStopReport:
    """Structured artifact when sub-agent fail-fast stops."""

    stop_reason: str
    trust_delta: float
    evidence: list[str]
    runner_next: RunnerMode
    partial_verdict: VerdictStatus
    gate: str = ""
    error_code: str = ""
    log_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubStopReport:
        return cls(
            stop_reason=str(data.get("stop_reason", "unknown")),
            trust_delta=float(data.get("trust_delta", -0.1)),
            evidence=list(data.get("evidence", [])),
            runner_next=data.get("runner_next", "llm"),
            partial_verdict=data.get("partial_verdict", "FAIL"),
            gate=str(data.get("gate", "")),
            error_code=str(data.get("error_code", "")),
            log_line=str(data.get("log_line", "")),
        )


@dataclass
class Verdict:
    gate: str
    status: VerdictStatus
    exit_code: int
    evidence: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    trust: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Verdict:
        return cls(
            gate=str(data.get("gate", "")),
            status=data.get("status", "FAIL"),
            exit_code=int(data.get("exit_code", 1)),
            evidence=list(data.get("evidence", [])),
            artifacts=dict(data.get("artifacts", {})),
            metrics=dict(data.get("metrics", {})),
            trust=dict(data.get("trust", {})),
        )


@dataclass
class TrustRecord:
    script: str
    status: ScriptStatus = "draft"
    trust_score: float = 0.5
    version: str = "0.1.0"
    tied_to_tag: bool = True
    last_tag: str = ""
    one_shot_success_rate: float = 0.0
    runs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)