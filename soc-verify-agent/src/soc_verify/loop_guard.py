"""Stalemate detection via failure signatures and transition patterns."""

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
    transitions: list[str] = field(default_factory=list)
    drift_history: list[float] = field(default_factory=list)
    stalemate: bool = False
    force_mode: str = ""
    stalemate_pattern: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signatures": self.signatures,
            "transitions": self.transitions,
            "drift_history": self.drift_history,
            "stalemate": self.stalemate,
            "force_mode": self.force_mode,
            "stalemate_pattern": self.stalemate_pattern,
            "same_failure_threshold": 3,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopGuardState:
        return cls(
            signatures=list(data.get("signatures", [])),
            transitions=list(data.get("transitions", [])),
            drift_history=[float(x) for x in (data.get("drift_history") or [])],
            stalemate=bool(data.get("stalemate", False)),
            force_mode=str(data.get("force_mode", "")),
            stalemate_pattern=str(data.get("stalemate_pattern", "")),
        )


def detect_stagnation_pattern(
    transitions: list[str],
    *,
    drift_history: list[float] | None = None,
) -> str:
    if len(transitions) >= 4:
        recent = transitions[-4:]
        if recent[0] == recent[2] and recent[1] == recent[3] and recent[0] != recent[1]:
            return "OSCILLATION"

    if drift_history and len(drift_history) >= 3:
        tail = drift_history[-3:]
        if max(tail) - min(tail) < 0.01:
            return "NO_DRIFT"

    return ""


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


def _apply_stalemate(state: LoopGuardState, pattern: str) -> None:
    if not pattern:
        return
    state.stalemate = True
    state.stalemate_pattern = pattern
    if pattern == "OSCILLATION":
        state.force_mode = "triage_narrow"
    elif pattern == "NO_DRIFT":
        state.force_mode = "resync_spec"
    else:
        state.force_mode = "llm_full"


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
            _apply_stalemate(state, "SPINNING")

    save_loop_guard(run_dir, state, cfg)
    return state


def record_transition(
    run_dir: Path,
    node: str,
    *,
    error_kind: str = "",
    next_node: str = "",
) -> LoopGuardState:
    state = load_loop_guard(run_dir)
    label = f"{node}:{error_kind or next_node or 'continue'}"
    state.transitions.append(label)
    pattern = detect_stagnation_pattern(state.transitions, drift_history=state.drift_history)
    if pattern:
        _apply_stalemate(state, pattern)
    save_loop_guard(run_dir, state)
    return state


def record_drift_score(run_dir: Path, drift_score: float) -> LoopGuardState:
    state = load_loop_guard(run_dir)
    state.drift_history.append(round(float(drift_score), 4))
    pattern = detect_stagnation_pattern(state.transitions, drift_history=state.drift_history)
    if pattern == "NO_DRIFT":
        _apply_stalemate(state, pattern)
    save_loop_guard(run_dir, state)
    return state