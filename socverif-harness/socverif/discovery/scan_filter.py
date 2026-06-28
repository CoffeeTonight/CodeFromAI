"""Path exclusion helpers for discovery — keeps self-harness scans focused."""
# goal_build_id = 12

from __future__ import annotations


def path_excluded(rel_parts: tuple[str, ...], exclude_dirs: frozenset[str]) -> bool:
    """Return True when a relative path falls under scan_exclude_dirs."""
    if not exclude_dirs:
        return False
    rel = "/".join(rel_parts)
    for ex in exclude_dirs:
        ex_parts = tuple(ex.split("/"))
        if rel_parts[: len(ex_parts)] == ex_parts:
            return True
        if ex in rel_parts:
            return True
        if rel == ex or rel.startswith(ex + "/"):
            return True
    return False