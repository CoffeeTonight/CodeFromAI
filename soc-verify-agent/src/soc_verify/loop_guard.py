"""Stalemate detection via failure signatures."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.models import SubStopReport, Verdict, load_yaml, save_yaml


@dataclass
class LoopGuardConfig:
    same_failure_threshold: int = 3
    signature_fields: list[str] = field(
        default_factory=lambda: ["gate", "error_code", "log_hash_8"]
    )


def log_hash_8(line: str) -> str:
    text = line.strip() or "(empty)"
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def build_signature(
    *,
    gate: str = "",
    error_code: str = "",
    log_line: str = "",
    verdict: Verdict | None = None,
    stop: SubStopReport | None = None,
) -> str:
    if stop is not None:
        gate = stop.gate or gate
        error_code = stop.error_code or stop.stop_reason
        log_line = stop.log_line or (stop.evidence[0] if stop.evidence else "")
    if verdict is not None:
        gate = verdict.gate or gate
        error_code = str(verdict.exit_code)
        log_line = verdict.evidence[0] if verdict.evidence else ""

    h = log_hash_8(log_line)
    return f"{gate}|{error_code}|{h}"


@dataclass
class LoopGuardState:
    signatures: list[str] = field(default_factory=list)
    stalemate: bool = False
    force_mode: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signatures": self.signatures,
            "stalemate": self.stalemate,
            "force_mode": self.force_mode,
            "same_failure_threshold": 3,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopGuardState:
        return cls(
            signatures=list(data.get("signatures", [])),
            stalemate=bool(data.get("stalemate", False)),
            force_mode=str(data.get("force_mode", "")),
        )


def load_loop_guard(run_dir: Path) -> LoopGuardState:
    path = run_dir / "loop_guard.yaml"
    data = load_yaml(path)
    if not data:
        return LoopGuardState()
    return LoopGuardState.from_dict(data)


def save_loop_guard(run_dir: Path, state: LoopGuardState, cfg: LoopGuardConfig | None = None) -> None:
    cfg = cfg or LoopGuardConfig()
    data = state.to_dict()
    data["same_failure_threshold"] = cfg.same_failure_threshold
    data["signature_fields"] = cfg.signature_fields
    data["on_stalemate"] = {
        "force_mode": "llm_full",
        "append_questions": True,
        "do_not": "auto_pass",
    }
    save_yaml(run_dir / "loop_guard.yaml", data)


def record_failure(
    run_dir: Path,
    signature: str,
    cfg: LoopGuardConfig | None = None,
) -> LoopGuardState:
    cfg = cfg or LoopGuardConfig()
    state = load_loop_guard(run_dir)
    state.signatures.append(signature)

    if len(state.signatures) >= cfg.same_failure_threshold:
        recent = state.signatures[-cfg.same_failure_threshold :]
        if len(set(recent)) == 1:
            state.stalemate = True
            state.force_mode = "llm_full"

    save_loop_guard(run_dir, state, cfg)
    return state