"""CLI progress reporting for hch-index."""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, TextIO


def format_duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60.0:
        return f"{seconds:.1f}s"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {secs}s"


def choose_auto_batch_size(source_count: int) -> int:
    """Smaller batches for very large filelists → more frequent progress."""
    if source_count >= 5000:
        return 8
    if source_count >= 2000:
        return 16
    if source_count >= 500:
        return 32
    if source_count >= 48:
        return 64
    return 0


class ProgressHeartbeat:
    """Emit periodic 'still running' phase lines during long synchronous work."""

    def __init__(
        self,
        on_phase: Optional[Callable[[str], None]],
        label: str,
        *,
        interval_sec: float = 20.0,
    ) -> None:
        self._on_phase = on_phase
        self._label = label
        self._interval = interval_sec
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._t0 = time.perf_counter()

    def __enter__(self) -> "ProgressHeartbeat":
        if not self._on_phase:
            return self
        def _loop() -> None:
            while not self._stop.wait(self._interval):
                elapsed = format_duration(time.perf_counter() - self._t0)
                self._on_phase(f"{self._label}… still running ({elapsed})")

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


class IndexProgressReporter:
    """Phase + per-file progress on stderr; summary for stdout."""

    def __init__(self, *, stream: Optional[TextIO] = None) -> None:
        self._stream = stream or sys.stderr
        self._tty = hasattr(self._stream, "isatty") and self._stream.isatty()
        self._t0 = time.perf_counter()
        self.started_at = datetime.now()
        self._last_len = 0
        self._milestone = 50

    def phase(self, message: str) -> None:
        self._end_line()
        print(f"[hch-index] {message}", file=self._stream, flush=True)

    def files(self, current: int, total: int, path: str = "") -> None:
        if total <= 0:
            return
        pct = 100.0 * current / total
        name = Path(path).name if path else ""
        tail = f" {name}" if name else ""
        line = f"[hch-index] sources: {current}/{total} ({pct:.0f}%){tail}"
        milestone = total >= 1000 and current > 0 and current % self._milestone == 0
        force_line = milestone or current >= total or not self._tty
        if self._tty and not force_line:
            pad = max(0, self._last_len - len(line))
            self._stream.write("\r" + line + " " * pad)
            self._stream.flush()
            self._last_len = len(line)
        else:
            self._end_line()
            print(line, file=self._stream, flush=True)
        if current >= total:
            self._last_len = 0

    def heartbeat(self, label: str, *, interval_sec: float = 20.0) -> ProgressHeartbeat:
        return ProgressHeartbeat(self.phase, label, interval_sec=interval_sec)

    def _end_line(self) -> None:
        if self._tty and self._last_len:
            self._stream.write("\n")
            self._stream.flush()
            self._last_len = 0

    def elapsed(self) -> float:
        return time.perf_counter() - self._t0

    def summary(
        self,
        *,
        instances: int,
        db_path: str,
        modules: Optional[int] = None,
    ) -> str:
        self._end_line()
        finished_at = datetime.now()
        elapsed = self.elapsed()
        lines = [
            f"Indexed {instances} instances -> {db_path}",
            f"Started:  {self.started_at:%Y-%m-%d %H:%M:%S}",
            f"Finished: {finished_at:%Y-%m-%d %H:%M:%S}",
            f"Elapsed:  {format_duration(elapsed)}",
        ]
        if modules is not None:
            lines.insert(1, f"Modules:  {modules}")
        return "\n".join(lines)

    def meta(self) -> dict[str, str]:
        finished_at = datetime.now()
        return {
            "index_started_at": self.started_at.isoformat(timespec="seconds"),
            "index_finished_at": finished_at.isoformat(timespec="seconds"),
            "index_elapsed_sec": f"{self.elapsed():.3f}",
        }