"""Resolve ``module_ref`` / module_id for instances under multi-def names."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

from hch.ingest.multi_def import module_ref
from hch.platform_paths import path_contains, path_to_db, paths_equal


def paths_for_module_name(
    module_name: str,
    mod_paths_by_name: Mapping[str, Sequence[str]],
) -> list[str]:
    raw = mod_paths_by_name.get(module_name) or ()
    out: list[str] = []
    seen: set[str] = set()
    for p in raw:
        key = path_to_db(p)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def resolve_instance_module_ref(
    module_name: str,
    *,
    edge_file: str = "",
    parent_module_file: str = "",
    parent_path: Optional[str] = None,
    sibling_index: int = 0,
    mod_paths_by_name: Optional[Mapping[str, Sequence[str]]] = None,
) -> str:
    """
    Pick ``filepath::module`` for a child instance.

    Priority: edge file matches a known definition path → parent-dir heuristic →
    deterministic sibling index among duplicate definitions.
    """
    paths = paths_for_module_name(module_name, mod_paths_by_name or {})
    if not paths:
        fp = edge_file or parent_module_file
        return module_ref(path_to_db(fp) if fp else "", module_name)

    if edge_file:
        edge_res = path_to_db(edge_file)
        for p in paths:
            if paths_equal(p, edge_res) or path_contains(edge_res, p) or path_contains(
                p, edge_res
            ):
                return module_ref(p, module_name)

    if parent_module_file:
        parent_dir = path_to_db(Path(parent_module_file).parent)
        local = [p for p in paths if path_contains(p, parent_dir)]
        if len(local) == 1:
            return module_ref(local[0], module_name)

    if len(paths) == 1:
        return module_ref(paths[0], module_name)

    idx = max(0, sibling_index) % len(paths)
    return module_ref(paths[idx], module_name)


def resolve_module_id(
    conn: sqlite3.Connection,
    module_name: str,
    *,
    module_ref_hint: str = "",
    inst_file: str = "",
    parent_path: Optional[str] = None,
) -> Optional[int]:
    """SQLite ``modules.id`` for an instance row."""
    if module_ref_hint:
        row = conn.execute(
            "SELECT id FROM modules WHERE module_ref = ? LIMIT 1",
            (module_ref_hint,),
        ).fetchone()
        if row:
            return int(row[0])

    if inst_file:
        row = conn.execute(
            """
            SELECT m.id FROM modules m
            JOIN files f ON f.id = m.definition_file_id
            WHERE m.module_name = ? AND f.filepath = ?
            LIMIT 1
            """,
            (module_name, inst_file),
        ).fetchone()
        if row:
            return int(row[0])

    rows = conn.execute(
        """
        SELECT m.id, f.filepath FROM modules m
        JOIN files f ON f.id = m.definition_file_id
        WHERE m.module_name = ?
        """,
        (module_name,),
    ).fetchall()
    if not rows:
        return None
    if len(rows) == 1:
        return int(rows[0][0])

    if parent_path:
        parent_leaf = parent_path.split(".")[-1]
        prow = conn.execute(
            """
            SELECT f.filepath FROM instances i
            JOIN files f ON f.id = i.filepath_id
            WHERE i.full_path = ? OR i.inst_leaf_name = ?
            LIMIT 1
            """,
            (parent_path, parent_leaf),
        ).fetchone()
        if prow and prow[0]:
            parent_dir = str(Path(prow[0]).parent)
            best = min(
                rows,
                key=lambda r: (
                    0 if parent_dir in str(r[1]) else 1,
                    len(str(r[1])),
                ),
            )
            return int(best[0])
    return int(rows[0][0])


def module_ref_from_id(conn: sqlite3.Connection, mod_id: int) -> str:
    row = conn.execute(
        "SELECT module_ref FROM modules WHERE id = ?",
        (mod_id,),
    ).fetchone()
    return row[0] if row else ""