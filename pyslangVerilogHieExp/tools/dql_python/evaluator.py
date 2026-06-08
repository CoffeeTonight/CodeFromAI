"""
evaluator.py - Evaluate parsed DQL AST against design instance dicts.
Must produce identical results to the JS/HTML matchesDQL + matchPattern + evaluateDQL.
"""

import re
from typing import Any, Dict, List, Union
from .parser import (
    DQLQuery, And, Or, Not, Comparison, InExpr, BarePattern,
    parse_dql, ast_to_dict
)

# ------------------------------------------------------------------
# matchPattern - the heart of ~ and bare pattern matching
# Must behave like the JS version in hierarchy_explorer.html
# ------------------------------------------------------------------

_WILDCARD_RE_CACHE: Dict[str, re.Pattern] = {}

def match_pattern(pattern: str, text: str, *, anchored: bool = False) -> bool:
    """
    High-fidelity glob-style wildcard matcher for ~ / !~ / bare patterns.
    
    Designed to be as close as possible to the JS matchPattern used in the
    original hierarchy_explorer.html.
    
    Rules:
    - * matches any sequence (including empty and dots)
    - ? matches any single character
    - Case-insensitive
    - By default "contains" style (no ^ $), matching observed JS usage for design search.
    - anchored=True forces full match (^...$)
    """
    if text is None:
        text = ""
    text = str(text)

    if not pattern or pattern == "*":
        return True

    # Fast exact path
    if "*" not in pattern and "?" not in pattern:
        if anchored:
            return pattern.lower() == text.lower()
        return pattern.lower() in text.lower()

    cache_key = (pattern, anchored)
    if cache_key not in _WILDCARD_RE_CACHE:
        escaped = re.escape(pattern)
        regex_src = escaped.replace(r"\*", ".*").replace(r"\?", ".")

        if anchored:
            regex_src = "^" + regex_src + "$"

        _WILDCARD_RE_CACHE[cache_key] = re.compile(regex_src, re.IGNORECASE | re.DOTALL)

    regex = _WILDCARD_RE_CACHE[cache_key]
    return bool(regex.search(text))


# ------------------------------------------------------------------
# Field extraction from instance
# The JS side uses different fields depending on context:
#   module, name (hierarchy), file, port (special: any port matches)
# ------------------------------------------------------------------

def get_field_value(instance: Dict[str, Any], field: str) -> Any:
    """
    Return the value for a field from the instance.
    Supports common keys used in the demo data and HTML explorer.
    """
    f = field.lower()
    if f in ("module",):
        return instance.get("module") or instance.get("mod") or ""
    if f in ("name", "hierarchy", "inst"):
        # "inst" = instantiated instance name (hierarchical path)
        # "name" / "hierarchy" are aliases for the same thing
        return instance.get("name") or instance.get("hierarchy") or instance.get("inst") or ""
    if f in ("file", "filepath", "source"):
        return instance.get("file") or instance.get("filepath") or instance.get("source") or ""
    if f == "port":
        # Special: for matching we check against the list of ports
        ports = instance.get("ports") or instance.get("port_list") or []
        if isinstance(ports, (list, tuple)):
            return ports
        if isinstance(ports, str):
            return [ports]
        return []
    # Unknown field: return the raw or empty
    return instance.get(field, "")


def field_matches(instance: Dict[str, Any], field: str, op: str, value: str) -> bool:
    """
    Perform one comparison: field op value
    """
    raw = get_field_value(instance, field)

    if field.lower() == "port":
        # For port field, the "value" must match ANY of the ports
        ports: List[str] = raw if isinstance(raw, list) else []
        if op == "=":
            return any(p == value for p in ports)
        if op == "!=":
            return all(p != value for p in ports)
        if op == "~":
            return any(match_pattern(value, p) for p in ports)
        if op == "!~":
            return all(not match_pattern(value, p) for p in ports)
        return False

    # Normal scalar fields
    text = str(raw) if raw is not None else ""

    if op == "=":
        return text.lower() == value.lower()
    if op == "!=":
        return text.lower() != value.lower()
    if op == "~":
        return match_pattern(value, text)
    if op == "!~":
        return not match_pattern(value, text)

    # Fallback
    return False


def evaluate_in(instance: Dict[str, Any], field: str, values: List[str], negated: bool) -> bool:
    """
    IN / NOT IN support, with wildcard pattern matching inside the list.

    This is required for JS HTML parity:
    `module in ("uart*", "spi")` should match modules that match the pattern "uart*"
    or are exactly "spi".
    """
    raw = get_field_value(instance, field)

    if field.lower() == "port":
        ports: List[str] = raw if isinstance(raw, list) else []
        def port_matches_any(p: str) -> bool:
            for v in values:
                if '*' in v or '?' in v:
                    if match_pattern(v, p):
                        return True
                else:
                    if p == v:
                        return True
            return False

        if negated:
            # NOT IN: none of the ports should match any value (pattern or exact)
            return all(not port_matches_any(p) for p in ports)
        else:
            return any(port_matches_any(p) for p in ports)

    else:
        # Normal scalar field (module, name, file, etc.)
        text = str(raw) if raw is not None else ""

        def value_matches(text_val: str, v: str) -> bool:
            if '*' in v or '?' in v:
                return match_pattern(v, text_val)
            else:
                return text_val.lower() == v.lower()

        if negated:
            # NOT IN: text should not match any of the values (exact or pattern)
            return all(not value_matches(text, v) for v in values)
        else:
            return any(value_matches(text, v) for v in values)


def evaluate(expr: Union[DQLQuery, And, Or, Not, Comparison, InExpr, BarePattern],
             instance: Dict[str, Any]) -> bool:
    """
    Recursively evaluate the AST against one instance dict.
    This is the core that must match JS evaluateDQL exactly.
    """
    if isinstance(expr, DQLQuery):
        return evaluate(expr.expr, instance)

    if isinstance(expr, And):
        return evaluate(expr.left, instance) and evaluate(expr.right, instance)

    if isinstance(expr, Or):
        return evaluate(expr.left, instance) or evaluate(expr.right, instance)

    if isinstance(expr, Not):
        return not evaluate(expr.expr, instance)

    if isinstance(expr, Comparison):
        return field_matches(instance, expr.field, expr.op, expr.value)

    if isinstance(expr, InExpr):
        return evaluate_in(instance, expr.field, expr.values, expr.negated)

    if isinstance(expr, BarePattern):
        # Bare pattern: In JS HTML explorer (especially B-mode), bare patterns like "uart*5*"
        # are expected to match against the visible hierarchy (name) preferentially.
        # Explicit "module ~" or "module in" remain strict to the module field.
        nam = str(get_field_value(instance, "name") or "")
        mod = str(get_field_value(instance, "module") or "")
        if match_pattern(expr.pattern, nam):
            return True
        return match_pattern(expr.pattern, mod)

    return False


# ------------------------------------------------------------------
# Public API used by dql_query.py and tests
# ------------------------------------------------------------------

def matches_dql(query: str, instance: Dict[str, Any]) -> bool:
    """High level: parse + evaluate. Mirrors JS matchesDQL as closely as possible."""
    if not query or not query.strip():
        return True   # empty query matches all (consistent with HTML explorer)
    try:
        ast = parse_dql(query)
        return evaluate(ast, instance)
    except Exception:
        # Strict on error (same spirit as many query UIs)
        return False


def get_matched_ports_for_query(query: str, instance: Dict[str, Any]) -> List[str]:
    """
    Accurate B-mode port expansion.
    For each concrete port on the instance, we create a temporary view where
    only that port exists, then re-evaluate the FULL query against it.
    
    This mirrors the spirit of the JS getMatchedPortsForQuery + port expansion logic.
    Only ports that make the entire (possibly complex) query true are returned.
    """
    ports = get_field_value(instance, "port")
    if not isinstance(ports, list) or len(ports) == 0:
        return []

    # Always do per-port full re-evaluation for maximum correctness with complex queries.
    # This is the reliable way to achieve JS-level B-mode behavior for AND/OR/NOT mixes.
    matched = []
    for p in ports:
        tmp = dict(instance)
        tmp["ports"] = [p]
        if matches_dql(query, tmp):
            matched.append(p)
    return matched


if __name__ == "__main__":
    # Quick self-test
    inst = {
        "name": "soc.cpu.uart05",
        "module": "uart_16550",
        "file": "uart/uart_16550.v",
        "ports": ["clk", "rst_n", "irq", "txd", "rxd", "cts", "rts"]
    }

    queries = [
        "module ~ \"uart*\"",
        "uart*",
        "port ~ \"irq\"",
        "port in (\"clk\", \"irq\")",
        "module ~ \"uart\" AND port ~ \"irq\"",
        "NOT port ~ \"tx*\"",
        "name ~ \"*cpu*\" AND port !~ \"rxd\"",
    ]
    for q in queries:
        m = matches_dql(q, inst)
        ports = get_matched_ports_for_query(q, inst) if "port" in q.lower() else []
        print(f"{m!s:5} | {q:45} | matched_ports={ports}")
