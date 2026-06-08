"""
Public matching interface for the Pure Python DQL parser (using Lark).
"""

from typing import List, Dict, Any, Optional
from .parser import parse_query
from .evaluator import evaluate_ast


def matches_dql(
    query: str,
    name: str,
    module_name: str = "",
    ports: Any = None,
    filepath: str = ""
) -> bool:
    """
    Main entry point for DQL matching.
    HTML의 matchesDQL과 동일한 동작을 목표로 함.
    """
    if not query or not query.strip():
        return True

    try:
        ast = parse_query(query)
        context = {
            "name": name,
            "module": module_name,
            "ports": _normalize_ports(ports),
            "filepath": filepath or "",
        }
        return evaluate_ast(ast, context)
    except Exception as e:
        print(f"[dql_python] Parse/Eval error: {e}")
        return False


def query_dql(
    query: str,
    instances: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    High-level query function.
    """
    if instances is None:
        raise ValueError("instances must be provided for query_dql in dql_python")

    results = []
    for inst in instances:
        if matches_dql(
            query,
            name=inst.get("name", ""),
            module_name=inst.get("module", ""),
            ports=inst.get("ports"),
            filepath=inst.get("filepath", ""),
        ):
            results.append(inst)
    return results


def _normalize_ports(ports: Any) -> List[str]:
    if not ports:
        return []
    if isinstance(ports, dict):
        return list(ports.keys())
    if isinstance(ports, (list, tuple)):
        return [str(p) for p in ports]
    return []


def _simple_fallback_match(query: str, name: str, module_name: str, ports: Any, filepath: str) -> bool:
    """Temporary fallback until full parser is complete."""
    q = query.lower()
    name_l = name.lower()
    module_l = (module_name or "").lower()
    port_names = [p.lower() for p in _normalize_ports(ports)]

    # Very basic support for development
    if "module" in q and "~" in q:
        # naive extraction
        import re
        m = re.search(r'module[^~]*~\s*"([^"]*)"', q)
        if m:
            pat = m.group(1).replace("*", "").lower()
            if pat and pat not in name_l:
                return False

    if "port" in q and "~" in q:
        m = re.search(r'port[^~]*~\s*"([^"]*)"', q)
        if m:
            pat = m.group(1).replace("*", "").lower()
            if pat and not any(pat in p for p in port_names):
                return False

    return True