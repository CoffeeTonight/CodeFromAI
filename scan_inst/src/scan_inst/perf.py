"""Performance helpers: auto low-memory, job resolution."""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_LOW_MEMORY_AUTO_THRESHOLD = 1500
DEFAULT_INCLUDE_WARM_MAX = 200
DEFAULT_BODY_PARAM_SCAN_MAX = 512 * 1024


def low_memory_auto_threshold() -> int:
    """Source count at which fused index build is enabled (0 = disabled)."""
    raw = os.environ.get("SCAN_INST_LOW_MEMORY_AUTO", "").strip()
    if raw.lower() in ("0", "off", "false", "no", "disable", "disabled"):
        return 0
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return DEFAULT_LOW_MEMORY_AUTO_THRESHOLD


def effective_low_memory(*, explicit: bool, num_sources: int) -> bool:
    if explicit:
        return True
    threshold = low_memory_auto_threshold()
    return threshold > 0 and num_sources >= threshold


def body_param_scan_max() -> int:
    """
    Max module body size (bytes) for scanning ``parameter``/``localparam`` decls.

    Bodies larger than this use header params only at index time (0 = always scan).
    """
    raw = os.environ.get("SCAN_INST_BODY_PARAM_SCAN_MAX", "").strip()
    if raw.lower() in ("0", "off", "false", "no", "disable", "disabled"):
        return 0
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return DEFAULT_BODY_PARAM_SCAN_MAX


def include_warm_enabled() -> bool:
    """Include warm is opt-in (``SCAN_INST_INCLUDE_WARM=1``)."""
    import os

    raw = os.environ.get("SCAN_INST_INCLUDE_WARM", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def log_large_module_skips() -> bool:
    """When true, stderr notes modules that skip body parameter collection."""
    raw = os.environ.get("SCAN_INST_LOG_LARGE_MODULES", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def slow_file_log_threshold_sec() -> Optional[float]:
    """
    Log per-file preprocess/scan timing when a source exceeds this many seconds.

    ``SCAN_INST_LOG_SLOW_FILES=1`` uses 10s; ``=30`` uses 30s; unset/0 disables.
    """
    raw = os.environ.get("SCAN_INST_LOG_SLOW_FILES", "").strip().lower()
    if raw in ("", "0", "off", "false", "no", "disable", "disabled"):
        return None
    if raw in ("1", "true", "yes", "on"):
        return 10.0
    try:
        return max(0.1, float(raw))
    except ValueError:
        return 10.0