"""Tier P: unroll constant-bound and parameter-resolved ``for`` generate loops."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

DEFAULT_MAX_GENERATE_LOOP = 256
_max_generate_loop = DEFAULT_MAX_GENERATE_LOOP


def set_max_generate_loop(n: int) -> None:
    global _max_generate_loop
    _max_generate_loop = max(1, int(n))


def _syntax_text(node: Any) -> str:
    if node is None:
        return ""
    if hasattr(node, "text"):
        return str(node.text)
    if hasattr(node, "valueText"):
        return str(node.valueText)
    return str(node).strip()


def _param_int(value: str) -> Optional[int]:
    text = (value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    m = re.search(r"(?:\d+'[bdh])?(\d+)\b", text, re.I)
    if m:
        return int(m.group(1))
    return None


def resolve_parameter_expression(
    expr: Any,
    param_map: Mapping[str, str],
) -> Optional[int]:
    """Fold simple constant parameter expressions to int."""
    if expr is None:
        return None
    lit = _integer_literal(expr)
    if lit is not None:
        return lit
    kind = str(getattr(expr, "kind", ""))
    if "Identifier" in kind:
        name = _syntax_text(getattr(expr, "identifier", None) or expr)
        if name in param_map:
            return _param_int(param_map[name])
        return None
    if "Unary" in kind and "Minus" in kind:
        v = resolve_parameter_expression(getattr(expr, "operand", None), param_map)
        return -v if v is not None else None
    if "Binary" in kind or "Add" in kind or "Subtract" in kind or "Multiply" in kind:
        left = resolve_parameter_expression(getattr(expr, "left", None), param_map)
        right = resolve_parameter_expression(getattr(expr, "right", None), param_map)
        if left is None or right is None:
            return None
        op = _syntax_text(getattr(expr, "operatorToken", None))
        if "+" in op:
            return left + right
        if "-" in op:
            return left - right
        if "*" in op:
            return left * right
    if "Parenthesized" in kind:
        return resolve_parameter_expression(
            getattr(expr, "expression", None), param_map
        )
    text = _syntax_text(expr).strip()
    if text in param_map:
        return _param_int(param_map[text])
    return None


def _integer_literal(expr: Any, param_map: Optional[Mapping[str, str]] = None) -> Optional[int]:
    if expr is None:
        return None
    if param_map is not None:
        resolved = resolve_parameter_expression(expr, param_map)
        if resolved is not None:
            return resolved
    kind = str(getattr(expr, "kind", ""))
    if "IntegerLiteral" in kind:
        lit = getattr(expr, "literal", None)
        text = _syntax_text(lit) if lit is not None else _syntax_text(expr)
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
    if "Parenthesized" in kind:
        return _integer_literal(getattr(expr, "expression", None), param_map)
    text = _syntax_text(expr).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return None


def _loop_step(iteration_expr: Any) -> int:
    if iteration_expr is None:
        return 1
    kind = str(getattr(iteration_expr, "kind", ""))
    if "Increment" in kind or "Postincrement" in kind or "Preincrement" in kind:
        return 1
    if "Decrement" in kind or "Postdecrement" in kind or "Predecrement" in kind:
        return -1
    if "Binary" in kind or "Assignment" in kind:
        right = _integer_literal(getattr(iteration_expr, "right", None))
        op = _syntax_text(getattr(iteration_expr, "operatorToken", None))
        if right is not None and "+" in op:
            return right
        if right is not None and "-" in op:
            return -right
    if "Assignment" in kind:
        rhs = getattr(iteration_expr, "right", None)
        rk = str(getattr(rhs, "kind", ""))
        if "Add" in rk:
            step = _integer_literal(getattr(rhs, "right", None))
            if step is not None:
                return step
        if "Subtract" in rk:
            step = _integer_literal(getattr(rhs, "right", None))
            if step is not None:
                return -step
    return 1


def loop_indices_for_generate(
    loop_node: Any,
    *,
    param_map: Optional[Mapping[str, str]] = None,
    max_iterations: Optional[int] = None,
) -> tuple[List[int], bool]:
    """
    Return genvar indices and whether bounds were fully resolved.

    Second value is False when falling back to a single iteration placeholder.
    """
    cap = max_iterations if max_iterations is not None else _max_generate_loop
    if loop_node is None or "LoopGenerate" not in str(getattr(loop_node, "kind", "")):
        return [0], False

    pmap = param_map or {}
    lo = _integer_literal(getattr(loop_node, "initialExpr", None), pmap)
    if lo is None:
        return [0], False

    step = _loop_step(getattr(loop_node, "iterationExpr", None))
    if step == 0:
        return [0], False

    stop = getattr(loop_node, "stopExpr", None)
    if stop is None:
        return [lo], True

    stop_kind = str(getattr(stop, "kind", ""))
    hi: Optional[int] = None
    inclusive = False

    if "LessThanEqual" in stop_kind:
        inclusive = True
        hi = _integer_literal(getattr(stop, "right", None), pmap)
    elif "LessThan" in stop_kind:
        hi = _integer_literal(getattr(stop, "right", None), pmap)
    elif "GreaterThanEqual" in stop_kind:
        inclusive = True
        hi = _integer_literal(getattr(stop, "left", None), pmap)
        lo, hi = _integer_literal(getattr(stop, "right", None), pmap), hi
    elif "GreaterThan" in stop_kind:
        hi = _integer_literal(getattr(stop, "left", None), pmap)
        lo, hi = _integer_literal(getattr(stop, "right", None), pmap), hi

    if hi is None:
        return [lo], False

    if step > 0:
        end = hi if inclusive else hi - 1
        if end < lo:
            return [lo], True
        indices = list(range(lo, end + 1, step))
    else:
        end = hi if inclusive else hi + 1
        if end > lo:
            return [lo], True
        indices = list(range(lo, end - 1, step))

    if len(indices) > cap:
        return indices[:cap], True
    return (indices if indices else [lo]), True


def loop_path_segment(label: str, index: int) -> str:
    base = label or "gen"
    return f"{base}[{index}]"


def if_generate_truth(
    node: Any,
    param_map: Mapping[str, str],
) -> Optional[bool]:
    """Return True/False when condition is constant; None if ambiguous."""
    if node is None or "IfGenerate" not in str(getattr(node, "kind", "")):
        return None
    cond = getattr(node, "condition", None)
    val = resolve_parameter_expression(cond, param_map)
    if val is not None:
        return val != 0
    raw = _syntax_text(cond)
    raw_lower = raw.lower()
    import re

    def _define_truth(name: str) -> Optional[bool]:
        key = name if name in param_map else name.upper()
        if key not in param_map and name not in param_map:
            return None
        val = str(param_map.get(key, param_map.get(name, "0"))).strip().lower()
        return val not in ("", "0", "false", "1'b0")

    ifdef_m = re.search(r"`?ifdef\s+([a-zA-Z_]\w*)", raw_lower, re.I)
    if ifdef_m:
        truth = _define_truth(ifdef_m.group(1))
        if truth is not None:
            return truth
    ifndef_m = re.search(r"`?ifndef\s+([a-zA-Z_]\w*)", raw_lower, re.I)
    if ifndef_m:
        truth = _define_truth(ifndef_m.group(1))
        if truth is not None:
            return not truth
    compact = raw_lower.replace(" ", "")
    if compact in ("1", "1'b1", "'b1", "true"):
        return True
    if compact in ("0", "1'b0", "'b0", "false"):
        return False
    return None


def case_generate_arms(
    node: Any,
    param_map: Mapping[str, str],
) -> List[tuple[str, Any]]:
    """Return (path_segment, clause) for each case generate item with a walkable clause."""
    if node is None or "CaseGenerate" not in str(getattr(node, "kind", "")):
        return []
    sel = resolve_parameter_expression(getattr(node, "condition", None), param_map)
    arms: List[tuple[str, Any]] = []
    for item in getattr(node, "items", None) or []:
        kind = str(getattr(item, "kind", ""))
        clause = getattr(item, "clause", None)
        if clause is None:
            continue
        if "Default" in kind:
            arms.append(("case_default", clause))
            continue
        matched = False
        labels: List[str] = []
        for expr in getattr(item, "expressions", None) or []:
            ev = resolve_parameter_expression(expr, param_map)
            if ev is not None:
                labels.append(str(ev))
                if sel is not None and ev == sel:
                    matched = True
            else:
                labels.append(_syntax_text(expr) or "expr")
        seg = f"case_{labels[0]}" if labels else "case_arm"
        if sel is None:
            arms.append((seg, clause))
        elif matched:
            arms.append((seg, clause))
    return arms


def _while_skipped_tokens(node: Any) -> List[tuple[str, str]]:
    """Best-effort (kind, text) from generate-block skipped *while* trivia."""
    begin = getattr(node, "block", None) or node
    begin = getattr(begin, "begin", None) or getattr(node, "begin", None)
    if begin is None:
        return []
    out: List[tuple[str, str]] = []
    for triv in getattr(begin, "trivia", None) or []:
        if "SkippedTokens" not in str(getattr(triv, "kind", "")):
            continue
        for tok in getattr(triv, "tokens", None) or []:
            out.append((str(getattr(tok, "kind", "")), _syntax_text(tok)))
    if not out and hasattr(node, "to_json"):
        import json

        try:
            data = json.loads(node.to_json())
            begin_j = (data.get("block") or data).get("begin") or data.get("begin") or {}
            for triv in begin_j.get("trivia") or []:
                if triv.get("kind") != "SkippedTokens":
                    continue
                for tok in triv.get("tokens") or []:
                    out.append((tok.get("kind", ""), tok.get("text", "")))
        except (json.JSONDecodeError, TypeError):
            pass
    return out


def while_generate_iterations(
    node: Any,
    param_map: Mapping[str, str],
    *,
    max_iterations: Optional[int] = None,
    skipped_tokens: Optional[List[tuple[str, str]]] = None,
) -> tuple[List[int], bool]:
    """
    Tier P ``while`` generate indices.

    Unrolls ``while (i < N)`` when *N* is constant; ``while (P)`` when *P* is a
    parameter; otherwise one placeholder ``[0]``.
    """
    cap = max_iterations if max_iterations is not None else _max_generate_loop
    if node is None:
        return [0], False

    kind = str(getattr(node, "kind", ""))
    if "While" in kind:
        cond = getattr(node, "condition", None)
        truth = resolve_parameter_expression(cond, param_map)
        if truth is not None and truth == 0:
            return [], True
        if truth is not None:
            return [0], True
        return [0], False

    toks = skipped_tokens if skipped_tokens is not None else _while_skipped_tokens(node)
    if not toks or not any("WhileKeyword" in k for k, _ in toks):
        return [0], False

    inner: List[tuple[str, str]] = []
    in_paren = False
    for k, t in toks:
        if "WhileKeyword" in k:
            in_paren = False
            continue
        if "OpenParenthesis" in k and not inner:
            in_paren = True
            continue
        if "CloseParenthesis" in k and in_paren:
            break
        if in_paren:
            inner.append((k, t))

    if len(inner) == 1 and "Identifier" in inner[0][0]:
        name = inner[0][1]
        if name in param_map:
            val = _param_int(param_map[name])
            if val is not None:
                return ([0], True) if val != 0 else ([], True)
        return [0], False

    if len(inner) >= 3 and "LessThan" in inner[1][0]:
        limit: Optional[int] = None
        if "IntegerLiteral" in inner[2][0]:
            lit = inner[2][1].strip()
            if lit.isdigit() or (lit.startswith("-") and lit[1:].isdigit()):
                limit = int(lit)
        elif "Identifier" in inner[2][0]:
            limit = _param_int(param_map.get(inner[2][1], ""))
        if limit is not None and limit > 0:
            indices = list(range(min(limit, cap)))
            return indices, True
        if limit == 0:
            return [], True

    return [0], False