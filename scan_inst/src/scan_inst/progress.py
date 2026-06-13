"""stderr progress reporting for scan-inst."""

from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
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


ProgressFn = Callable[[str], None]


class ProgressReporter:
    """Lightweight phase lines on stderr."""

    def __init__(self, *, stream: Optional[TextIO] = None, enabled: bool = True) -> None:
        self._stream = stream or sys.stderr
        self._enabled = enabled
        self._t0 = time.perf_counter()

    def phase(self, message: str) -> None:
        if not self._enabled:
            return
        print(f"[scan-inst] {message}", file=self._stream, flush=True)

    def elapsed(self) -> float:
        return time.perf_counter() - self._t0


class ProgressHeartbeat:
    """Emit periodic still-running lines during long synchronous work."""

    def __init__(
        self,
        on_phase: ProgressFn,
        label: str,
        *,
        interval_sec: float = 15.0,
        enabled: bool = True,
    ) -> None:
        self._on_phase = on_phase
        self._label = label
        self._interval = interval_sec
        self._enabled = enabled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._t0 = time.perf_counter()

    def __enter__(self) -> "ProgressHeartbeat":
        if not self._enabled:
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


@contextmanager
def null_progress() -> Iterator[None]:
    yield


def progress_callback(reporter: Optional[ProgressReporter]) -> Optional[ProgressFn]:
    if reporter is None or not reporter._enabled:
        return None
    return reporter.phase