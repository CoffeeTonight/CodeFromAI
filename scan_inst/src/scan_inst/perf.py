"""Performance helpers: auto low-memory, job resolution."""

from __future__ import annotations

import os

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


def log_large_module_skips() -> bool:
    """When true, stderr notes modules that skip body parameter collection."""
    raw = os.environ.get("SCAN_INST_LOG_LARGE_MODULES", "").strip().lower()
    return raw in ("1", "true", "yes", "on")