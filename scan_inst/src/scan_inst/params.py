"""Parameter / localparam parsing and constant folding for generate."""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, Optional, Tuple


def _skip_balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    if start >= len(text) or text[start] != open_ch:
        return start
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _param_int(val: str) -> Optional[int]:
    val = val.strip().strip('"').strip("'")
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    if re.fullmatch(r"\d+'[bdhBDH][0-9a-fA-FxzXZ_]+", val):
        if val.lower().startswith("0b") or "'b" in val.lower() or "'B" in val:
            bits = val.split("'")[-1].lstrip("bB")
            try:
                return int(bits.replace("_", ""), 2)
            except ValueError:
                return None
        if "'d" in val or "'D" in val:
            try:
                return int(val.split("'")[-1].lstrip("dD").replace("_", ""))
            except ValueError:
                return None
        if "'h" in val.lower():
            try:
                return int(val.split("'")[-1].lstrip("hH"), 16)
            except ValueError:
                return None
    return None

_PARAM_PAIR_RE = re.compile(
    r"(?:\b(?:parameter|localparam)\b\s+)?(?:\w+\s+)?"
    r"([A-Za-z_]\w*)\s*=",
    re.IGNORECASE,
)
_OVERRIDE_PAIR_RE = re.compile(
    r"\.?\s*([A-Za-z_]\w*)\s*\(\s*([^)]+)\s*\)",
    re.IGNORECASE,
)


def _scan_param_value(text: str, start: int) -> Tuple[Optional[str], int]:
    i = start
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return None, i
    depth = 0
    val_start = i
    while i < n:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch in ",;" and depth == 0:
            return text[val_start:i].strip(), i
        i += 1
    return text[val_start:i].strip(), i


def _find_top_level_op(expr: str, op: str) -> Optional[int]:
    depth = 0
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == op:
            return i
        i += 1
    return None


def parse_param_pairs(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in _PARAM_PAIR_RE.finditer(text):
        val, _ = _scan_param_value(text, m.end())
        if val:
            out[m.group(1)] = val
    return out


def parse_param_overrides(text: str) -> Dict[str, str]:
    """Parse ``#(.N(P), x(1+2*(1+TWO)+1))`` with balanced parentheses."""
    out: Dict[str, str] = {}
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if text[i] == ".":
            i += 1
        m = re.match(r"([A-Za-z_]\w*)", text[i:])
        if not m:
            i += 1
            continue
        name = m.group(1)
        i += m.end()
        while i < n and text[i].isspace():
            i += 1
        if i >= n or text[i] != "(":
            continue
        end = _skip_balanced(text, i, "(", ")")
        if end <= i + 1:
            i = end
            continue
        out[name] = text[i + 1 : end - 1].strip()
        i = end
    return out


def split_module_header(chunk: str) -> Tuple[str, str]:
    """Return (header_param_text, module_body) from text after module name."""
    i = 0
    n = len(chunk)
    while i < n and chunk[i].isspace():
        i += 1
    header = ""
    if i < n and chunk[i] == "#":
        i += 1
        while i < n and chunk[i].isspace():
            i += 1
        if i < n and chunk[i] == "(":
            end = _skip_balanced(chunk, i, "(", ")")
            header = chunk[i + 1 : end - 1] if end > i + 1 else ""
            i = end
    while i < n and chunk[i].isspace():
        i += 1
    if i < n and chunk[i] == "(":
        i = _skip_balanced(chunk, i, "(", ")")
    while i < n and chunk[i].isspace():
        i += 1
    if i < n and chunk[i] == ";":
        i += 1
    return header, chunk[i:]


def collect_module_params(header_text: str, body: str) -> Dict[str, str]:
    """Module header + body parameter/localparam declarations (defaults)."""
    params = parse_param_pairs(header_text)
    for m in re.finditer(
        r"(?:\b(?:parameter|localparam)\b\s+(?:\w+\s+)?[^;]+;)",
        body,
        re.IGNORECASE,
    ):
        params.update(parse_param_pairs(m.group(0)))
    return params


def _tokenize_expr(expr: str) -> list[str]:
    tokens: list[str] = []
    i, n = 0, len(expr)
    while i < n:
        if expr[i].isspace():
            i += 1
            continue
        if expr[i] in "()+-*/":
            tokens.append(expr[i])
            i += 1
            continue
        m = re.match(
            r"(<=|>=|==|!=|<|>)|(\d+'[bdhBDH][0-9a-fA-FxzXZ_]+|-?\d+)|([A-Za-z_]\w*)",
            expr[i:],
            re.IGNORECASE,
        )
        if not m:
            i += 1
            continue
        tok = m.group(0)
        tokens.append(tok)
        i += len(tok)
    return tokens


def _eval_tokens(tokens: list[str], ctx: Mapping[str, str]) -> Optional[int]:
    if not tokens:
        return None

    def value_at(idx: int) -> Tuple[Optional[int], int]:
        if idx >= len(tokens):
            return None, idx
        tok = tokens[idx]
        if tok == "(":
            v, j = expr_at(idx + 1)
            if j >= len(tokens) or tokens[j] != ")":
                return None, j
            return v, j + 1
        if tok == "-":
            v, j = value_at(idx + 1)
            return (-v if v is not None else None), j
        if tok == "+":
            return value_at(idx + 1)
        if re.fullmatch(r"-?\d+", tok):
            return int(tok), idx + 1
        if re.fullmatch(r"\d+'[bdhBDH]", tok, re.I) and idx + 1 < len(tokens):
            lit = tok + tokens[idx + 1]
            v = _param_int(lit)
            return v, idx + 2
        v = _param_int(tok)
        if v is not None:
            return v, idx + 1
        if tok in ctx:
            return _param_int(ctx[tok]), idx + 1
        return None, idx + 1

    def term_at(idx: int) -> Tuple[Optional[int], int]:
        left, j = value_at(idx)
        while j < len(tokens) and tokens[j] == "*":
            right, j = value_at(j + 1)
            if left is None or right is None:
                return None, j
            left = left * right
        return left, j

    def sum_at(idx: int) -> Tuple[Optional[int], int]:
        left, j = term_at(idx)
        while j < len(tokens) and tokens[j] in ("+", "-"):
            op = tokens[j]
            right, j = term_at(j + 1)
            if left is None or right is None:
                return None, j
            left = left + right if op == "+" else left - right
        return left, j

    def expr_at(idx: int) -> Tuple[Optional[int], int]:
        return sum_at(idx)

    val, pos = expr_at(0)
    if pos != len(tokens):
        return None
    return val


def resolve_param_expr(expr: str, ctx: Mapping[str, str]) -> Optional[int]:
    expr = expr.strip()
    if not expr:
        return None
    if expr in ctx:
        v = _param_int(ctx[expr])
        if v is not None:
            return v
    qpos = _find_top_level_op(expr, "?")
    if qpos is not None:
        cond = expr[:qpos].strip()
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1].strip()
        rest = expr[qpos + 1 :]
        cpos = _find_top_level_op(rest, ":")
        if cpos is not None:
            t_expr = rest[:cpos].strip()
            f_expr = rest[cpos + 1 :].strip()
            cval = expr_is_true(cond, ctx)
            if cval is None:
                return None
            return resolve_param_expr(t_expr if cval else f_expr, ctx)
    v = _param_int(expr)
    if v is not None:
        return v
    return _eval_tokens(_tokenize_expr(expr), ctx)


def expr_is_true(expr: str, ctx: Mapping[str, str]) -> Optional[bool]:
    e = expr.strip()
    if e.lower() in ("1", "1'b1", "1'h1", "'1", "true"):
        return True
    if e.lower() in ("0", "1'b0", "1'h0", "'0", "false"):
        return False
    for op in (">=", "<=", "!=", "==", ">", "<"):
        parts = e.split(op, 1)
        if len(parts) != 2:
            continue
        left = resolve_param_expr(parts[0].strip(), ctx)
        right = resolve_param_expr(parts[1].strip(), ctx)
        if left is None or right is None:
            continue
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
        if op == "!=":
            return left != right
        if op == "==":
            return left == right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
    v = resolve_param_expr(e, ctx)
    if v is not None:
        return v != 0
    return None


def resolve_param_map(
    declarations: Mapping[str, str],
    *,
    overrides: Optional[Mapping[str, str]] = None,
    parent: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """
    Fold parameter/localparam declarations with optional parent scope and
    instance #(.) overrides. Returns name -> numeric string when possible.
    """
    raw: Dict[str, str] = dict(declarations)
    if overrides:
        raw.update(overrides)
    resolved: Dict[str, str] = {}
    if parent:
        for k, v in parent.items():
            iv = resolve_param_expr(v, parent) if not str(v).isdigit() else int(v)
            if iv is not None:
                resolved[k] = str(iv)

    for _ in range(len(raw) + 2):
        changed = False
        for name, expr in raw.items():
            ctx = {k: v for k, v in raw.items() if k != name}
            ctx.update(resolved)
            iv = resolve_param_expr(expr, ctx)
            if iv is None:
                continue
            new_v = str(iv)
            if resolved.get(name) != new_v:
                resolved[name] = new_v
                changed = True
        if not changed:
            break
    for name, expr in raw.items():
        if name not in resolved:
            resolved[name] = expr.strip()
    return resolved


def parse_bound_token(token: str, param_map: Mapping[str, str]) -> Optional[int]:
    token = token.strip()
    v = resolve_param_expr(token, param_map)
    if v is not None:
        return v
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    return None