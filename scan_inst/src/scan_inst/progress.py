"""stderr progress reporting for scan-inst."""

from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
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


ProgressFn = Callable[[str], None]


def format_work_location(
    file_path: str,
    *,
    index: Optional[int] = None,
    total: Optional[int] = None,
) -> str:
    """Short folder + file label for heartbeat / progress detail."""
    p = Path(str(file_path).replace("\\", "/"))
    parts = [x for x in p.parent.parts if x]
    if len(parts) > 2:
        folder = "/".join(parts[-2:])
    elif parts:
        folder = "/".join(parts)
    else:
        folder = "."
    label = f"folder: {folder} | file: {p.name}"
    if index is not None and total is not None:
        label = f"{label} ({index}/{total})"
    return label


def split_progress_detail(message: str) -> Optional[str]:
    """Return the detail suffix after `` — `` when present."""
    if " — " not in message:
        return None
    return message.split(" — ", 1)[1].strip() or None


class ProgressReporter:
    """Lightweight phase lines on stderr."""

    def __init__(self, *, stream: Optional[TextIO] = None, enabled: bool = True) -> None:
        self._stream = stream or sys.stderr
        self._enabled = enabled
        self._t0 = time.perf_counter()
        self._lock = threading.Lock()
        self._filelist_label = ""
        self._location = ""

    def phase(self, message: str) -> None:
        if not self._enabled:
            return
        print(f"[scan-inst] {message}", file=self._stream, flush=True)

    def set_filelist(self, filelist_path: str) -> None:
        with self._lock:
            self._filelist_label = Path(filelist_path).name or filelist_path

    def set_location(self, detail: str) -> None:
        with self._lock:
            self._location = detail.strip()

    def absorb_progress(self, message: str) -> None:
        """Update location detail from a progress line suffix."""
        suffix = split_progress_detail(message)
        if suffix is not None:
            self.set_location(suffix)

    def get_detail(self) -> str:
        with self._lock:
            parts: list[str] = []
            if self._filelist_label:
                parts.append(f"filelist: {self._filelist_label}")
            if self._location:
                parts.append(self._location)
            return " | ".join(parts)

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
        get_detail: Optional[Callable[[], str]] = None,
    ) -> None:
        self._on_phase = on_phase
        self._label = label
        self._interval = interval_sec
        self._enabled = enabled
        self._get_detail = get_detail
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._t0 = time.perf_counter()

    def __enter__(self) -> "ProgressHeartbeat":
        if not self._enabled:
            return self
        def _loop() -> None:
            while not self._stop.wait(self._interval):
                elapsed = format_duration(time.perf_counter() - self._t0)
                detail = self._get_detail() if self._get_detail else ""
                if detail:
                    self._on_phase(
                        f"{self._label}… still running ({elapsed}) — {detail}"
                    )
                else:
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

    def _emit(message: str) -> None:
        reporter.phase(message)
        reporter.absorb_progress(message)

    return _emit