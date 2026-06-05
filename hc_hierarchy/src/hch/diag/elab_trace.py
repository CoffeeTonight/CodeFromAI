"""Structured JSONL trace for Tier E pipeline failure points."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def elab_trace_from_env() -> Optional["ElabTrace"]:
    raw = (os.environ.get("HCH_ELAB_TRACE") or "").strip()
    if not raw or raw in ("0", "false", "no"):
        return None
    path = raw if raw not in ("1", "true", "yes") else ""
    return ElabTrace(path or None)


@dataclass
class ElabTrace:
    """Append JSON lines at each Tier E decision / failure point."""

    log_path: Optional[str] = None
    _events: List[Dict[str, Any]] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def _default_path(self) -> Path:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        root = Path(__file__).resolve().parents[3]
        log_dir = root / "logs" / "elab_trace"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"tier_e_{stamp}.jsonl"

    def event(
        self,
        stage: str,
        *,
        status: str = "ok",
        detail: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        row: Dict[str, Any] = {
            "t_ms": round((time.perf_counter() - self._t0) * 1000, 1),
            "stage": stage,
            "status": status,
        }
        if detail:
            row["detail"] = detail
        if error:
            row["error"] = error
        self._events.append(row)
        if self.log_path:
            path = Path(self.log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def flush_summary(self) -> Path:
        path = Path(self.log_path) if self.log_path else self._default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "event_count": len(self._events),
            "events": self._events,
        }
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self.log_path = str(path)
        return path