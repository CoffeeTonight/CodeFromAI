"""Read-only hierarchy API over SQLite index (shared by GUI and web)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from hch.apps.hierarchy_view import (
    fetch_db_depth_stats,
    fetch_subtree_depth_stats,
    format_index_depth_summary,
    format_selection_depth_line,
    format_subtree_text,
    meta_map,
)
from hch.query.dql.planner import apply_post_filters, plan_dql
from hch.query.dql.results import format_rows_plain, format_rows_text


def _blackbox_files_from_meta(raw: Dict[str, str]) -> List[str]:
    from hch.ingest.kit_blackbox import kit_blackbox_source_paths

    return sorted(kit_blackbox_source_paths(raw))


def _missing_files_from_meta(
    raw: Dict[str, str],
    *,
    exclude_paths: Optional[Set[str]] = None,
) -> List[str]:
    """Paths from filelist / parse meta that were missing at index time."""
    found: set[str] = set()
    skip = {str(p).replace("\\", "/") for p in (exclude_paths or set())}
    fl_errs = raw.get("filelist_errors", "")
    if fl_errs:
        try:
            errs = json.loads(fl_errs)
            if isinstance(errs, list):
                for entry in errs:
                    text = str(entry)
                    for prefix in ("Source not found:", "Filelist not found:"):
                        if prefix in text:
                            path = text.split(":", 1)[1].strip()
                            norm = path.replace("\\", "/")
                            if norm not in skip:
                                found.add(path)
        except json.JSONDecodeError:
            pass
    pe = raw.get("parse_errors_json", "")
    if pe:
        try:
            by_file = json.loads(pe)
            if isinstance(by_file, dict):
                for path, entry in by_file.items():
                    if isinstance(entry, dict) and entry.get("status") == "missing":
                        norm = str(path).replace("\\", "/")
                        if norm not in skip:
                            found.add(str(path))
        except json.JSONDecodeError:
            pass
    return sorted(found)


def _parse_tier(inst_tags_json: Optional[str]) -> str:
    if not inst_tags_json:
        return "full"
    try:
        tags = json.loads(inst_tags_json)
    except json.JSONDecodeError:
        return "full"
    if isinstance(tags, dict):
        return str(tags.get("parse_tier") or "full")
    return "full"


def _parse_ports(port_json: Optional[str]) -> List[str]:
    if not port_json:
        return []
    try:
        loaded = json.loads(port_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    out: List[str] = []
    for p in loaded:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict) and p.get("name"):
            out.append(str(p["name"]))
    return out


class HierarchyDbService:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def meta(self) -> Dict[str, Any]:
        rows = self.conn.execute("SELECT key, value FROM meta ORDER BY key").fetchall()
        data = {r["key"]: r["value"] for r in rows}
        data["database"] = str(self.db_path)
        data["instance_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM instances"
        ).fetchone()[0]
        data["module_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM modules"
        ).fetchone()[0]
        json_keys = (
            "warnings_json",
            "unresolved_modules_json",
            "defines_json",
            "elab_succeeded",
            "ifdef_variant_diff_json",
            "top_modules_json",
            "top_modules_all_json",
            "top_inference",
            "source_status_json",
            "parse_diagnostics_json",
            "unsupported_filelist_opts_json",
            "filelist_diff_json",
            "slang_options_json",
            "elab_param_instance_count",
        )
        for key in json_keys:
            if key in data:
                try:
                    alias = key.replace("_json", "")
                    data[alias] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass
        tier = data.get("tier", "P")
        src = data.get("hierarchy_source", "ast")
        elab = data.get("elab_succeeded", "")
        badge = f"Tier {tier}"
        if src:
            badge = f"{badge} · {src}"
        if elab == "0":
            badge = f"{badge} · elab failed"
        data["parse_tier_badge"] = badge
        blackbox_files = _blackbox_files_from_meta(data)
        data["blackbox_files"] = blackbox_files
        data["blackbox_file_count"] = len(blackbox_files)
        bb_skip = {p.replace("\\", "/") for p in blackbox_files}
        missing = _missing_files_from_meta(data, exclude_paths=bb_skip)
        data["missing_files"] = missing
        data["missing_file_count"] = len(missing)
        if "filelist_errors" in data:
            try:
                data["filelist_errors_list"] = json.loads(data["filelist_errors"])
            except json.JSONDecodeError:
                data["filelist_errors_list"] = []
        depth_stats = fetch_db_depth_stats(self.conn)
        data["db_min_depth"] = depth_stats["min_depth"]
        data["db_max_depth"] = depth_stats["max_depth"]
        data["depth_summary"] = format_index_depth_summary(self.conn)
        meta = meta_map(self.conn)
        data["index_max_depth"] = meta.get("index_max_depth")
        data["depth_shallow_limit"] = meta.get("depth_shallow_limit")
        data["depth_anchor_extra"] = meta.get("depth_anchor_extra")
        return data

    def subtree_view(self, root_path: str) -> Optional[Dict[str, Any]]:
        root_path = (root_path or "").strip()
        if not root_path:
            return None
        stats = fetch_subtree_depth_stats(self.conn, root_path)
        if not stats:
            return None
        text = format_subtree_text(self.conn, root_path)
        return {
            "root_path": root_path,
            "text": text,
            "line_count": text.count("\n") + 1 if text else 0,
            "selection_summary": format_selection_depth_line(self.conn, root_path),
            "stats": stats,
        }

    def _index_top_modules(self) -> List[str]:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = 'top_modules_json' LIMIT 1"
        ).fetchone()
        if not row or not row[0]:
            return []
        try:
            loaded = json.loads(row[0])
        except json.JSONDecodeError:
            return []
        if not isinstance(loaded, list):
            return []
        return [str(t).strip() for t in loaded if str(t).strip()]

    def tree_children(self, parent_path: Optional[str] = None) -> List[Dict[str, Any]]:
        if not parent_path:
            tops = self._index_top_modules()
            if tops:
                placeholders = ",".join("?" for _ in tops)
                cur = self.conn.execute(
                    f"""
                    SELECT i.full_path, i.inst_leaf_name, m.module_name, i.depth,
                           i.port_json, f.filepath, i.inst_tags_json,
                           (SELECT COUNT(*) FROM instances c WHERE c.parent_path = i.full_path) AS child_count
                    FROM instances i
                    JOIN modules m ON m.id = i.module_id
                    LEFT JOIN files f ON f.id = i.filepath_id
                    WHERE i.full_path IN ({placeholders})
                    ORDER BY i.full_path
                    """,
                    tops,
                )
            else:
                cur = self.conn.execute(
                    """
                    SELECT i.full_path, i.inst_leaf_name, m.module_name, i.depth,
                           i.port_json, f.filepath, i.inst_tags_json,
                           (SELECT COUNT(*) FROM instances c WHERE c.parent_path = i.full_path) AS child_count
                    FROM instances i
                    JOIN modules m ON m.id = i.module_id
                    LEFT JOIN files f ON f.id = i.filepath_id
                    WHERE i.parent_path IS NULL OR i.parent_path = ''
                    ORDER BY i.full_path
                    """
                )
        else:
            cur = self.conn.execute(
                """
                SELECT i.full_path, i.inst_leaf_name, m.module_name, i.depth,
                       i.port_json, f.filepath, i.inst_tags_json,
                       (SELECT COUNT(*) FROM instances c WHERE c.parent_path = i.full_path) AS child_count
                FROM instances i
                JOIN modules m ON m.id = i.module_id
                LEFT JOIN files f ON f.id = i.filepath_id
                WHERE i.parent_path = ?
                ORDER BY i.full_path
                """,
                (parent_path,),
            )
        return [
            {
                "full_path": r["full_path"],
                "leaf": r["inst_leaf_name"],
                "module": r["module_name"],
                "depth": r["depth"],
                "filepath": r["filepath"] or "",
                "ports": _parse_ports(r["port_json"]),
                "has_children": r["child_count"] > 0,
                "parse_tier": _parse_tier(r["inst_tags_json"]),
            }
            for r in cur.fetchall()
        ]

    def deepen(
        self,
        under_path: str,
        *,
        extra_depth: Optional[int] = None,
        full_subtree: bool = True,
        jobs: int = 0,
    ) -> Dict[str, Any]:
        from hch.index.deepen import deepen_branch

        result = deepen_branch(
            str(self.db_path),
            under_path,
            extra_depth=extra_depth,
            full_subtree=full_subtree,
            jobs=jobs,
        )
        return {
            "under_path": result.under_path,
            "files_parsed": result.files_parsed,
            "modules_upgraded": result.modules_upgraded,
            "instances_before": result.instances_before,
            "instances_after": result.instances_after,
            "deepened_paths": list(result.deepened_paths),
            "instance_count": self.conn.execute(
                "SELECT COUNT(*) FROM instances"
            ).fetchone()[0],
        }

    def instance_detail(self, full_path: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT i.full_path, i.inst_leaf_name, m.module_name, i.depth,
                   i.parent_path, i.port_json, f.filepath, m.port_json AS mod_ports,
                   i.inst_tags_json
            FROM instances i
            JOIN modules m ON m.id = i.module_id
            LEFT JOIN files f ON f.id = i.filepath_id
            WHERE i.full_path = ?
            """,
            (full_path,),
        ).fetchone()
        if not row:
            return None
        ports = _parse_ports(row["port_json"])
        if not ports:
            ports = _parse_ports(row["mod_ports"])
        return {
            "full_path": row["full_path"],
            "leaf": row["inst_leaf_name"],
            "module": row["module_name"],
            "depth": row["depth"],
            "parent_path": row["parent_path"],
            "filepath": row["filepath"] or "",
            "ports": ports,
            "parse_tier": _parse_tier(row["inst_tags_json"]),
        }

    def run_dql(
        self, query: str, *, limit: int = 5000, text_format: Optional[str] = None
    ) -> Dict[str, Any]:
        q = query.strip()
        if not q:
            return {"query": q, "rows": [], "count": 0}
        plan = plan_dql(q)
        rows = [dict(r) for r in self.conn.execute(plan.sql, plan.params).fetchall()]
        rows = apply_post_filters(rows, plan)
        if len(rows) > limit:
            rows = rows[:limit]
            truncated = True
        else:
            truncated = False
        out_rows: List[Dict[str, Any]] = []
        for r in rows:
            out_rows.append(
                {
                    "full_path": r.get("full_path", ""),
                    "inst": r.get("inst_leaf_name", ""),
                    "module": r.get("module_name", ""),
                    "filepath": r.get("filepath") or "",
                    "depth": r.get("depth", 0),
                    "ports": _parse_ports(r.get("port_json")),
                    "parent_path": r.get("parent_path"),
                    "parse_tier": _parse_tier(r.get("inst_tags_json")),
                }
            )
        payload: Dict[str, Any] = {
            "query": q,
            "rows": out_rows,
            "count": len(out_rows),
            "truncated": truncated,
        }
        if text_format in ("text", "tsv"):
            payload["text"] = format_rows_text(rows, query=q)
        elif text_format == "plain":
            payload["text"] = format_rows_plain(rows, query=q)
        return payload

    def allowed_source(self, filepath: str) -> bool:
        from hch.platform_paths import path_to_db

        fp = path_to_db(filepath)
        row = self.conn.execute(
            "SELECT 1 FROM files WHERE filepath = ? LIMIT 1",
            (fp,),
        ).fetchone()
        return row is not None

    def read_source(
        self,
        filepath: str,
        *,
        max_bytes: int = 512_000,
        highlight: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from hch.platform_paths import path_to_db, resolve_path

        fp = path_to_db(filepath)
        if not fp and not str(filepath or "").strip():
            return {
                "filepath": "",
                "content": "",
                "missing": True,
                "error": "No source file linked to this instance",
                "truncated": False,
                "size": 0,
                "highlights": [],
            }
        if not self.allowed_source(fp):
            return {
                "filepath": fp or str(filepath),
                "content": "",
                "missing": True,
                "error": f"Source file not in index: {filepath}",
                "truncated": False,
                "size": 0,
                "highlights": [h for h in (highlight or []) if h],
            }
        path = resolve_path(fp)
        if not path.is_file():
            return {
                "filepath": fp,
                "content": "",
                "missing": True,
                "error": f"Source file not found on disk: {fp}",
                "truncated": False,
                "size": 0,
                "highlights": [h for h in (highlight or []) if h],
            }
        data = path.read_bytes()
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return {
            "filepath": fp,
            "content": text,
            "truncated": truncated,
            "size": path.stat().st_size,
            "highlights": [h for h in (highlight or []) if h],
        }