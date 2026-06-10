"""CLI progress reporting for hch-index."""

from __future__ import annotations

import sys
import threading
import time
import warnings
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Optional, TextIO


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


def choose_auto_batch_size(source_count: int, *, jobs: int = 1) -> int:
    """Batch size for checkpointed parse; parallel jobs use larger batches."""
    parallel = jobs > 1
    if source_count >= 5000:
        return 64 if parallel else 8
    if source_count >= 2000:
        return 64 if parallel else 16
    if source_count >= 500:
        return 64 if parallel else 32
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


class _ProgressSafeStderr:
    """End the active progress line before unrelated stderr writes."""

    def __init__(self, reporter: "IndexProgressReporter", underlying: TextIO) -> None:
        self._reporter = reporter
        self._underlying = underlying
        self._in_write = False

    def write(self, s: str) -> int:
        if not self._in_write and s:
            needs_prefix = (
                s not in ("\n", "\r")
                and not s.startswith("\n")
                and self._reporter.needs_newline
            )
            self._reporter.end_line()
            if needs_prefix:
                s = "\n" + s
        self._in_write = True
        try:
            return self._underlying.write(s)
        finally:
            self._in_write = False

    def flush(self) -> None:
        self._underlying.flush()

    def isatty(self) -> bool:
        fn = getattr(self._underlying, "isatty", None)
        return bool(fn and fn())

    def fileno(self) -> int:
        return self._underlying.fileno()

    def __getattr__(self, name: str):
        return getattr(self._underlying, name)


@contextmanager
def progress_stderr_guard(
    reporter: Optional["IndexProgressReporter"],
) -> Iterator[None]:
    """Wrap sys.stderr so warnings/logs do not append to a progress line."""
    if reporter is None:
        yield
        return
    old_stderr = sys.stderr
    old_showwarning = warnings.showwarning

    def _showwarning(message, category, filename, lineno, file=None, line=None):
        reporter.end_line()
        target = file if file is not None else sys.__stderr__
        old_showwarning(
            message, category, filename, lineno, file=target, line=line
        )

    sys.stderr = _ProgressSafeStderr(reporter, sys.__stderr__)
    warnings.showwarning = _showwarning
    try:
        yield
    finally:
        reporter.end_line()
        sys.stderr = old_stderr
        warnings.showwarning = old_showwarning


class IndexProgressReporter:
    """Phase + per-file progress on stderr; summary for stdout."""

    def __init__(self, *, stream: Optional[TextIO] = None) -> None:
        self._stream_override = stream
        self._needs_nl = False
        self._t0 = time.perf_counter()
        self.started_at = datetime.now()

    @property
    def _stream(self) -> TextIO:
        return self._stream_override or sys.__stderr__

    @property
    def needs_newline(self) -> bool:
        return self._needs_nl

    def phase(self, message: str) -> None:
        self.end_line()
        print(f"[hch-index] {message}", file=self._stream, flush=True)
        self._needs_nl = False

    def files(self, current: int, total: int, path: str = "") -> None:
        if total <= 0:
            return
        self.end_line()
        pct = 100.0 * current / total
        name = Path(path).name if path else ""
        tail = f" {name}" if name else ""
        line = f"[hch-index] sources: {current}/{total} ({pct:.0f}%){tail}"
        print(line, file=self._stream, flush=True)
        self._needs_nl = False

    def heartbeat(self, label: str, *, interval_sec: float = 20.0) -> ProgressHeartbeat:
        return ProgressHeartbeat(self.phase, label, interval_sec=interval_sec)

    def end_line(self) -> None:
        """Finish an in-progress stderr line before unrelated output."""
        if not self._needs_nl:
            return
        print(file=self._stream, flush=True)
        self._needs_nl = False

    def elapsed(self) -> float:
        return time.perf_counter() - self._t0

    def summary(
        self,
        *,
        instances: int,
        db_path: str,
        modules: Optional[int] = None,
    ) -> str:
        self.end_line()
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