"""LLM invocation telemetry — model, tokens, latency per node (paper Methods)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ContextManager


LLM_TELEMETRY_NAME = "llm_telemetry.jsonl"


class LlmCallTimer:
    """Context manager for latency measurement."""

    def __init__(self) -> None:
        self.start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> "LlmCallTimer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = round((time.perf_counter() - self.start) * 1000, 2)


def timer() -> ContextManager[LlmCallTimer]:
    return LlmCallTimer()


def _extract_usage(resp: dict[str, Any] | None) -> dict[str, int | None]:
    if not resp:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    usage = resp.get("usage") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def append_llm_telemetry(
    run_dir: Path,
    *,
    node: str = "",
    task: str = "",
    mode: str = "",
    model: str = "",
    invoked: bool = False,
    message: str = "",
    latency_ms: float | None = None,
    raw_response: dict[str, Any] | None = None,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    usage = _extract_usage(raw_response)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "node": node,
        "task": task,
        "mode": mode,
        "model": model,
        "invoked": invoked,
        "message": message,
        "latency_ms": latency_ms,
        **usage,
    }
    path = run_dir / LLM_TELEMETRY_NAME
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def load_llm_telemetry(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / LLM_TELEMETRY_NAME
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out