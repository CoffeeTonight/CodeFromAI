"""Minimal DQL → SQL planner for hc_hierarchy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SqlPlan:
    sql: str
    params: List[Any]
    post_filter_lastnode: bool = False
    post_filter_expand_ports: bool = False
    row_limit: Optional[int] = None


def _glob_to_like(pattern: str) -> str:
    return pattern.replace("*", "%").replace("?", "_")


def plan_simple_dql(expr: str) -> SqlPlan:
    """
    Subset:  field ~ "pat"  AND ...  ; field in {path, module, port, filepath}
    Optional: lastnode (leaf filter within result set)
    """
    from hch.query.dql.modifiers import extract_query_modifiers

    expr, qmods = extract_query_modifiers(expr)
    lastnode = qmods.lastnode

    clauses: List[str] = []
    params: List[Any] = []

    for part in re.split(r"\s+AND\s+", expr, flags=re.IGNORECASE):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'(\w+)\s*~\s*"([^"]*)"', part)
        if not m:
            raise ValueError(f"Unsupported DQL clause: {part}")
        field, pat = m.group(1), m.group(2)
        like = _glob_to_like(pat)
        if field in ("path", "hierarchy", "name"):
            clauses.append("i.full_path LIKE ? ESCAPE '\\'")
            params.append(like)
        elif field == "parent":
            clauses.append("i.parent_path LIKE ? ESCAPE '\\'")
            params.append(like)
        elif field in ("inst", "instance"):
            clauses.append("i.inst_leaf_name LIKE ? ESCAPE '\\'")
            params.append(like)
        elif field == "module":
            clauses.append("m.module_name LIKE ? ESCAPE '\\'")
            params.append(like)
        elif field in ("filepath", "file", "filename"):
            clauses.append("f.filepath LIKE ? ESCAPE '\\'")
            params.append(like)
        elif field == "port":
            clauses.append("(m.port_json LIKE ? OR i.param_json LIKE ?)")
            params.extend([f"%{pat.replace('*', '%')}%", f"%{pat}%"])
        else:
            m_num = re.match(
                r"(depth|node_count)\s*(==|!=|<=|>=|<|>|=)\s*(\d+)",
                part,
                flags=re.IGNORECASE,
            )
            if m_num:
                name, op, raw = m_num.group(1).lower(), m_num.group(2), int(m_num.group(3))
                if op == "==":
                    op = "="
                col = (
                    "(LENGTH(i.full_path) - LENGTH(REPLACE(i.full_path, '.', '')))"
                    if name == "node_count"
                    else "i.depth"
                )
                if op == "=":
                    clauses.append(f"{col} = ?")
                elif op == "!=":
                    clauses.append(f"{col} != ?")
                elif op == "<":
                    clauses.append(f"{col} < ?")
                elif op == "<=":
                    clauses.append(f"{col} <= ?")
                elif op == ">":
                    clauses.append(f"{col} > ?")
                elif op == ">=":
                    clauses.append(f"{col} >= ?")
                params.append(raw)
                continue
            raise ValueError(f"Unknown DQL field: {field}")

    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
        SELECT i.full_path, i.inst_leaf_name, m.module_name, f.filepath,
               i.depth, i.parent_path, i.port_json
        FROM instances i
        JOIN modules m ON m.id = i.module_id
        LEFT JOIN files f ON f.id = i.filepath_id
        WHERE {where}
        ORDER BY i.full_path
    """
    return SqlPlan(
        sql=sql,
        params=params,
        post_filter_lastnode=lastnode,
        post_filter_expand_ports=qmods.expand_ports,
    )


def plan_dql(expr: str) -> SqlPlan:
    """Lark AST → SQL (OR, ^=, port index). Falls back to plan_simple_dql on parse errors."""
    try:
        from hch.query.dql.sql_compiler import plan_dql as _compile

        return _compile(expr)
    except Exception:
        return plan_simple_dql(expr)


def apply_lastnode(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from hch.query.dql.modifiers import apply_lastnode as _apply

    return _apply(rows)


def apply_post_filters(rows: List[Dict[str, Any]], plan: SqlPlan) -> List[Dict[str, Any]]:
    from hch.query.dql.modifiers import apply_post_filters as _apply

    return _apply(
        rows,
        lastnode=plan.post_filter_lastnode,
        expand_ports=plan.post_filter_expand_ports,
    )


