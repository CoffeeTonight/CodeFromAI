"""
DQL — Design Query Language (Python-only, Lark parser).
"""

from .parser import (
    parse_dql,
    DQLQuery,
    And,
    Or,
    Not,
    Comparison,
    InExpr,
    BarePattern,
    ast_to_dict,
)
from .evaluator import (
    matches_dql,
    evaluate,
    match_pattern,
    get_field_value,
    get_matched_ports_for_query,
)
from typing import Any, Dict, List

from .evaluator import match_pattern as _mp
from .parser import parse_dql as _parse_dql


def _has_bare_pattern(ast) -> bool:
    if not ast:
        return False

    def walk(node):
        if hasattr(node, "pattern") and node.pattern:
            return True
        for child in (
            getattr(node, "left", None),
            getattr(node, "right", None),
            getattr(node, "expr", None),
        ):
            if child and walk(child):
                return True
        if isinstance(node, (list, tuple)):
            for c in node:
                if walk(c):
                    return True
        return False

    return walk(ast)


def _any_pattern_matches_name(ast, name_val: str) -> bool:
    if not ast:
        return False

    def walk(node):
        if hasattr(node, "pattern") and node.pattern:
            if _mp(node.pattern, name_val):
                return True
        if hasattr(node, "values"):
            for v in getattr(node, "values", []):
                if ("*" in str(v) or "?" in str(v)) and _mp(str(v), name_val):
                    return True
        if hasattr(node, "value") and (
            "*" in str(getattr(node, "value", "")) or "?" in str(getattr(node, "value", ""))
        ):
            if _mp(str(getattr(node, "value", "")), name_val):
                return True
        for child in (
            getattr(node, "left", None),
            getattr(node, "right", None),
            getattr(node, "expr", None),
        ):
            if child and walk(child):
                return True
        if isinstance(node, (list, tuple)):
            for c in node:
                if walk(c):
                    return True
        return False

    return walk(ast)


def query_dql(
    query: str,
    instances: List[Dict[str, Any]],
    port_mode: bool = False,
    default_field: str = "module",
) -> List[Dict[str, Any]]:
    if not instances:
        return []

    results: List[Dict[str, Any]] = []
    q_lower = (query or "").lower()
    has_port_condition = "port" in q_lower

    for inst in instances:
        if port_mode and has_port_condition:
            tmp = dict(inst)
            tmp["ports"] = []
            full_match = matches_dql(query, inst)
            relaxed_match = matches_dql(query, tmp)
            bmode_fuzzy_match = False
            if not (full_match or relaxed_match):
                try:
                    ast = _parse_dql(query)
                    name_val = str(get_field_value(inst, "name") or "")
                    if _has_bare_pattern(ast) and _any_pattern_matches_name(ast, name_val):
                        bmode_fuzzy_match = True
                except Exception:
                    pass
            if not (full_match or relaxed_match or bmode_fuzzy_match):
                continue
            matched_ports = get_matched_ports_for_query(query, inst) or []
            if matched_ports:
                name = inst.get("name") or inst.get("hierarchy") or ""
                for p in matched_ports:
                    expanded = dict(inst)
                    expanded["hierarchy"] = f"{name}.{p}" if name else p
                    expanded["_port"] = p
                    results.append(expanded)
        else:
            if not matches_dql(query, inst):
                continue
            if port_mode and ("port" in q_lower or "port" in str(inst.get("ports", ""))):
                matched_ports = get_matched_ports_for_query(query, inst) or inst.get("ports", [])
                name = inst.get("name") or inst.get("hierarchy") or ""
                for p in matched_ports:
                    expanded = dict(inst)
                    expanded["hierarchy"] = f"{name}.{p}" if name else p
                    expanded["_port"] = p
                    results.append(expanded)
            else:
                results.append(dict(inst))

    return results


__all__ = [
    "parse_dql",
    "matches_dql",
    "query_dql",
    "evaluate",
    "match_pattern",
    "DQLQuery",
    "And",
    "Or",
    "Not",
    "Comparison",
    "InExpr",
    "BarePattern",
    "ast_to_dict",
    "get_matched_ports_for_query",
]