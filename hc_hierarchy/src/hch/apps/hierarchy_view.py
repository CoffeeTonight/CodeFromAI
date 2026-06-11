"""Shared hierarchy text + depth summaries (GUI and web)."""

from __future__ import annotations

import sqlite3
from typing import List, Optional


def _module_name(conn: sqlite3.Connection, module_id: int) -> str:
    row = conn.execute(
        "SELECT module_name FROM modules WHERE id = ?", (module_id,)
    ).fetchone()
    return row[0] if row else "?"


def fetch_db_depth_stats(conn: sqlite3.Connection) -> dict:
    """Aggregate depth stats for all instances in the DB."""
    row = conn.execute(
        "SELECT COUNT(*), MIN(depth), MAX(depth) FROM instances"
    ).fetchone()
    count = int(row[0] or 0)
    if count == 0:
        return {"count": 0, "min_depth": None, "max_depth": None}
    return {
        "count": count,
        "min_depth": int(row[1]),
        "max_depth": int(row[2]),
    }


def fetch_subtree_depth_stats(
    conn: sqlite3.Connection, root_path: str
) -> Optional[dict]:
    """Depth stats for *root_path* and all descendants."""
    root_path = root_path.strip()
    if not root_path:
        return None
    root_row = conn.execute(
        "SELECT depth FROM instances WHERE full_path = ?", (root_path,)
    ).fetchone()
    if not root_row:
        return None
    base_depth = int(root_row[0])
    row = conn.execute(
        """
        SELECT COUNT(*), MIN(depth), MAX(depth)
        FROM instances
        WHERE full_path = ? OR full_path LIKE ?
        """,
        (root_path, f"{root_path}.%"),
    ).fetchone()
    count = int(row[0] or 0)
    max_depth = int(row[2]) if row[2] is not None else base_depth
    return {
        "count": count,
        "base_depth": base_depth,
        "max_depth": max_depth,
        "relative_max": max(0, max_depth - base_depth),
    }


def meta_map(conn: sqlite3.Connection) -> dict:
    return {
        str(k): str(v)
        for k, v in conn.execute("SELECT key, value FROM meta").fetchall()
    }


def format_index_depth_summary(conn: sqlite3.Connection) -> str:
    """One-line DB + index depth policy summary."""
    stats = fetch_db_depth_stats(conn)
    meta = meta_map(conn)
    parts: List[str] = [f"instances: {stats['count']}"]
    if stats["max_depth"] is not None:
        parts.append(f"DB depth: {stats['min_depth']}–{stats['max_depth']}")
    else:
        parts.append("DB depth: (empty)")
    if meta.get("index_max_depth"):
        parts.append(f"index cap: {meta['index_max_depth']}")
    if meta.get("depth_shallow_limit"):
        parts.append(f"shallow: {meta['depth_shallow_limit']}")
    if meta.get("depth_anchor_extra"):
        parts.append(f"anchor +{meta['depth_anchor_extra']}")
    return " · ".join(parts)


def format_selection_depth_line(
    conn: sqlite3.Connection, root_path: str
) -> str:
    """One-line depth summary for the selected instance subtree."""
    sub = fetch_subtree_depth_stats(conn, root_path)
    if not sub:
        return ""
    return (
        f"selected: depth {sub['base_depth']}, "
        f"subtree {sub['count']} inst, +{sub['relative_max']} below"
    )


def format_subtree_text(conn: sqlite3.Connection, root_path: str) -> str:
    """Indented instance paths under *root_path* (includes root)."""
    root_path = root_path.strip()
    if not root_path:
        return ""
    rows = conn.execute(
        """
        SELECT full_path, inst_leaf_name, module_id, depth
        FROM instances
        WHERE full_path = ? OR full_path LIKE ?
        ORDER BY full_path
        """,
        (root_path, f"{root_path}.%"),
    ).fetchall()
    if not rows:
        return root_path
    base_depth = rows[0][3]
    lines: List[str] = []
    for fp, leaf, mid, depth in rows:
        mod = _module_name(conn, mid)
        indent = "  " * max(0, int(depth) - int(base_depth))
        lines.append(f"{indent}{fp}  ({mod})")
    return "\n".join(lines)


# Backward-compatible alias used by GUI tests.
format_subtree_clipboard = format_subtree_text