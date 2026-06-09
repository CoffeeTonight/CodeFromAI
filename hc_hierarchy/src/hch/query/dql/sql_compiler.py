"""Compile DQL AST to parameterized SQLite."""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from hch.query.dql.parser import (
    And,
    BarePattern,
    Comparison,
    DQLQuery,
    Expr,
    InExpr,
    Not,
    Or,
    parse_dql,
)
from hch.query.dql.modifiers import extract_query_modifiers
from hch.query.dql.planner import SqlPlan


def _glob_to_like(pattern: str) -> str:
    return pattern.replace("*", "%").replace("?", "_")


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _count_or_nodes(expr: Expr) -> int:
    if isinstance(expr, Or):
        return 1 + _count_or_nodes(expr.left) + _count_or_nodes(expr.right)
    if isinstance(expr, And):
        return _count_or_nodes(expr.left) + _count_or_nodes(expr.right)
    if isinstance(expr, Not):
        return _count_or_nodes(expr.expr)
    return 0


def _flatten_or_branches(expr: Expr) -> List[Expr]:
    if isinstance(expr, Or):
        return _flatten_or_branches(expr.left) + _flatten_or_branches(expr.right)
    return [expr]


def _try_compile_or_union(expr: Or) -> Optional[Tuple[str, List[Any]]]:
    """Wide OR of simple comparisons → UNION (better index use per branch)."""
    branches = _flatten_or_branches(expr)
    if len(branches) < 3:
        return None
    parts: List[str] = []
    params: List[Any] = []
    for branch in branches:
        if isinstance(branch, Comparison):
            sql, p = _compile_comparison(branch)
        elif isinstance(branch, BarePattern):
            sql, p = _compile_comparison(
                Comparison(field="inst", op="~", value=branch.pattern)
            )
        else:
            return None
        parts.append(
            "SELECT i.id FROM instances i "
            "JOIN modules m ON m.id = i.module_id "
            f"LEFT JOIN files f ON f.id = i.filepath_id WHERE {sql}"
        )
        params.extend(p)
    union = " UNION ".join(parts)
    return f"i.id IN ({union})", params


def _compile_expr(expr: Expr) -> Tuple[str, List[Any]]:
    if isinstance(expr, Or):
        union_sql = _try_compile_or_union(expr)
        if union_sql is not None:
            return union_sql
        l_sql, l_p = _compile_expr(expr.left)
        r_sql, r_p = _compile_expr(expr.right)
        return f"({l_sql}) OR ({r_sql})", l_p + r_p
    if isinstance(expr, And):
        l_sql, l_p = _compile_expr(expr.left)
        r_sql, r_p = _compile_expr(expr.right)
        return f"({l_sql}) AND ({r_sql})", l_p + r_p
    if isinstance(expr, Not):
        inner, params = _compile_expr(expr.expr)
        return f"NOT ({inner})", params
    if isinstance(expr, BarePattern):
        return _compile_comparison(
            Comparison(field="inst", op="~", value=expr.pattern)
        )
    if isinstance(expr, Comparison):
        return _compile_comparison(expr)
    if isinstance(expr, InExpr):
        return _compile_in(expr)
    raise TypeError(f"Unsupported expr: {type(expr)}")


def _path_column() -> str:
    return "i.full_path"


def _path_dot_count_sql() -> str:
    """Number of ``.`` in ``full_path`` (instance hierarchy depth by path)."""
    return "(LENGTH(i.full_path) - LENGTH(REPLACE(i.full_path, '.', '')))"


def _compile_int_field(col: str, op: str, val: str, field_name: str) -> Tuple[str, List[Any]]:
    try:
        n = int(val)
    except ValueError as e:
        raise ValueError(f"{field_name} value must be integer: {val!r}") from e
    if op == "=":
        return f"{col} = ?", [n]
    if op == "!=":
        return f"{col} != ?", [n]
    if op == "<":
        return f"{col} < ?", [n]
    if op == "<=":
        return f"{col} <= ?", [n]
    if op == ">":
        return f"{col} > ?", [n]
    if op == ">=":
        return f"{col} >= ?", [n]
    raise ValueError(f"Unsupported {field_name} operator: {op}")


def _compile_comparison(c: Comparison) -> Tuple[str, List[Any]]:
    field = c.field.lower()
    op = c.op
    val = c.value

    if field in ("inst", "instance"):
        col = "i.inst_leaf_name"
        if op == "^=":
            prefix = _escape_like(val.rstrip("*"))
            return f"{col} LIKE ? ESCAPE '\\'", [prefix + "%"]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "!~":
            return f"{col} NOT LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]

    if field == "parent":
        col = "i.parent_path"
        if op == "^=":
            prefix = _escape_like(val.rstrip("*"))
            return f"{col} LIKE ? ESCAPE '\\'", [prefix + "%"]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]

    if field in ("path", "hierarchy", "name"):
        col = _path_column()
        if op == "^=":
            prefix = _escape_like(val.rstrip("*"))
            return f"{col} LIKE ? ESCAPE '\\'", [prefix + "%"]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "!~":
            return f"{col} NOT LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]

    if field in ("module_ref", "modref"):
        from hch.platform_paths import normalize_dql_path_pattern

        val = normalize_dql_path_pattern(val)
        col = "COALESCE(i.module_ref, m.module_ref)"
        if op == "^=":
            return f"{col} LIKE ? ESCAPE '\\'", [_escape_like(val.rstrip("*")) + "%"]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]

    if field == "module":
        col = "m.module_name"
        if op == "^=":
            return f"{col} LIKE ? ESCAPE '\\'", [_escape_like(val.rstrip("*")) + "%"]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "!~":
            return f"{col} NOT LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]

    if field in ("file", "filepath", "filename"):
        from hch.platform_paths import normalize_dql_path_pattern

        val = normalize_dql_path_pattern(val)
        col = "f.filepath"
        if op == "^=":
            return f"{col} LIKE ? ESCAPE '\\'", [_escape_like(val.rstrip("*")) + "%"]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "!~":
            return f"{col} NOT LIKE ? ESCAPE '\\'", [_glob_to_like(val)]
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]

    if field == "depth":
        return _compile_int_field("i.depth", op, val, "depth")

    if field == "node_count":
        return _compile_int_field(_path_dot_count_sql(), op, val, "node_count")

    if field in ("kind", "module_kind"):
        col = "m.module_kind"
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]

    if field == "child_kind":
        col = "COALESCE(i.child_kind, 'module')"
        if op == "=":
            return f"{col} = ?", [val]
        if op == "!=":
            return f"{col} != ?", [val]
        if op == "~":
            return f"{col} LIKE ? ESCAPE '\\'", [_glob_to_like(val)]

    if field in ("from_macro", "macro_inst"):
        tag = "json_extract(i.inst_tags_json, '$.from_macro')"
        if op == "=" and val.lower() in ("1", "true", "yes"):
            return f"({tag} = 1 OR {tag} = true)", []
        if op == "=" and val.lower() in ("0", "false", "no"):
            return f"({tag} IS NULL OR {tag} = 0 OR {tag} = false)", []
        if op == "!=":
            return f"NOT ({tag} = 1 OR {tag} = true)", []

    if field in ("in_generate", "via_bind"):
        tag = f"json_extract(i.inst_tags_json, '$.{field}')"
        if op == "=" and val.lower() in ("1", "true", "yes"):
            return f"({tag} = 1 OR {tag} = true)", []
        if op == "=" and val.lower() in ("0", "false", "no"):
            return f"({tag} IS NULL OR {tag} = 0 OR {tag} = false)", []

    if field == "param":
        if op == "~":
            like = f"%{val.replace('*', '%')}%"
            return (
                "(m.param_json LIKE ? OR i.param_json LIKE ?)",
                [like, like],
            )
        if op == "=":
            needle = f'%"{val}"%'
            return (
                "(m.param_json LIKE ? OR i.param_json LIKE ?)",
                [needle, needle],
            )

    if field in ("port_path", "path.port"):
        concat = "(i.full_path || '.' || ip.port_name)"
        if op == "^=":
            prefix = _escape_like(val.rstrip("*"))
            return (
                "EXISTS (SELECT 1 FROM instance_ports ip "
                f"WHERE ip.instance_id = i.id AND {concat} LIKE ? ESCAPE '\\')",
                [prefix + "%"],
            )
        if op == "~":
            return (
                "EXISTS (SELECT 1 FROM instance_ports ip "
                f"WHERE ip.instance_id = i.id AND {concat} LIKE ? ESCAPE '\\')",
                [_glob_to_like(val)],
            )
        if op == "=":
            return (
                "EXISTS (SELECT 1 FROM instance_ports ip "
                f"WHERE ip.instance_id = i.id AND {concat} = ?)",
                [val],
            )

    if field == "port":
        if op == "~":
            like = _glob_to_like(val)
            return (
                "EXISTS (SELECT 1 FROM instance_ports ip "
                "WHERE ip.instance_id = i.id AND ip.port_name LIKE ? ESCAPE '\\')",
                [like],
            )
        if op == "=":
            return (
                "EXISTS (SELECT 1 FROM instance_ports ip "
                "WHERE ip.instance_id = i.id AND ip.port_name = ?)",
                [val],
            )
        if op == "!=":
            return (
                "NOT EXISTS (SELECT 1 FROM instance_ports ip "
                "WHERE ip.instance_id = i.id AND ip.port_name = ?)",
                [val],
            )

    raise ValueError(f"Unsupported comparison: {field} {op} {val!r}")


def _compile_in(inc: InExpr) -> Tuple[str, List[Any]]:
    if not inc.values:
        return ("0", [])
    field = inc.field.lower()
    placeholders = ",".join("?" * len(inc.values))
    neg = "NOT " if inc.negated else ""

    if field in ("module_ref", "modref"):
        return (
            f"COALESCE(i.module_ref, m.module_ref) {neg}IN ({placeholders})",
            list(inc.values),
        )
    if field == "module":
        return (f"m.module_name {neg}IN ({placeholders})", list(inc.values))
    if field in ("inst", "instance"):
        return (f"i.inst_leaf_name {neg}IN ({placeholders})", list(inc.values))
    if field in ("file", "filepath", "filename"):
        return (f"f.filepath {neg}IN ({placeholders})", list(inc.values))
    if field == "port":
        sub = (
            f"EXISTS (SELECT 1 FROM instance_ports ip "
            f"WHERE ip.instance_id = i.id AND ip.port_name {neg}IN ({placeholders}))"
        )
        return (sub, list(inc.values))
    if field in ("path", "hierarchy", "name"):
        return (f"{_path_column()} {neg}IN ({placeholders})", list(inc.values))
    raise ValueError(f"IN not supported for field: {field}")


_BASE_SELECT = """
    SELECT i.full_path, i.inst_leaf_name, m.module_name, f.filepath,
           i.depth, i.parent_path, i.port_json
    FROM instances i
    JOIN modules m ON m.id = i.module_id
    LEFT JOIN files f ON f.id = i.filepath_id
"""


def _extract_port_path_filter(expr: str) -> tuple[Optional[str], Optional[str]]:
    for field in ("port_path", "path.port"):
        m = re.search(
            rf'{field}\s*(=|\^=|~)\s*"([^"]*)"',
            expr,
            flags=re.IGNORECASE,
        )
        if m:
            return m.group(2), m.group(1)
    return None, None


def plan_dql(expr: str) -> SqlPlan:
    """Parse DQL with Lark and compile to SQL (preferred entry)."""
    cleaned, qmods = extract_query_modifiers(expr)
    row_limit: int | None = None
    port_path_filter: Optional[str] = None
    port_path_filter_op: Optional[str] = None
    if not cleaned:
        where, params = "1=1", []
    else:
        ast = parse_dql(cleaned)
        where, params = _compile_expr(ast.expr)
        if _count_or_nodes(ast.expr) >= 4:
            row_limit = 8000
        if qmods.expand_ports:
            port_path_filter, port_path_filter_op = _extract_port_path_filter(cleaned)
    sql = f"{_BASE_SELECT} WHERE {where} ORDER BY i.full_path"
    if row_limit is not None:
        sql += " LIMIT ?"
        params = list(params) + [row_limit]
    return SqlPlan(
        sql=sql,
        params=params,
        post_filter_lastnode=qmods.lastnode,
        post_filter_expand_ports=qmods.expand_ports,
        port_path_filter=port_path_filter,
        port_path_filter_op=port_path_filter_op,
        row_limit=row_limit,
    )