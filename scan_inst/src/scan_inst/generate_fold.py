"""Best-effort generate if/for folding before instance scan."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

from scan_inst.params import expr_is_true, parse_bound_token

_IDENT = r"[A-Za-z_]\w*"
_KEYWORDS = frozenset(
    {
        "module", "endmodule", "generate", "endgenerate", "if", "else", "for",
        "while", "begin", "end", "genvar", "parameter", "localparam", "assign",
        "wire", "logic", "reg", "input", "output", "inout", "always", "initial",
    }
)
_INSTANCE_PREFIX_RE = re.compile(
    rf"\b({_IDENT})\s+(?:#\([^()]*\)\s+)?({_IDENT})(?=\s*[\[(;])",
    re.IGNORECASE,
)

_GEN_BLOCK_RE = re.compile(
    r"\bgenerate\b(.*?)\bendgenerate\b",
    re.IGNORECASE | re.DOTALL,
)
_FOR_RE = re.compile(
    r"\bfor\s*\(\s*(?:genvar\s+)?([A-Za-z_]\w*)\s*=\s*([^;]+);\s*"
    r"([^;]+)\s*;\s*(?:\1\s*\+\+\s*|\1\s*=\s*\1\s*\+\s*1\s*)\s*\)\s*"
    r"begin(?:\s*:\s*([A-Za-z_]\w*))?\s*(.*?)\bend\b",
    re.IGNORECASE | re.DOTALL,
)
_FOR_STMT_RE = re.compile(
    r"\bfor\s*\(\s*(?:genvar\s+)?([A-Za-z_]\w*)\s*=\s*([^;]+);\s*"
    r"([^;]+)\s*;\s*(?:\1\s*\+\+\s*|\1\s*=\s*\1\s*\+\s*1\s*)\s*\)\s*"
    r"(?!begin\b)([^;]+;)",
    re.IGNORECASE | re.DOTALL,
)
_IF_RE = re.compile(
    r"\bif\s*\(\s*([^)]+)\s*\)\s*begin\s*(?::\s*([A-Za-z_]\w*))?\s*(.*?)\bend"
    r"(?:\s*else\s*begin\s*(?::\s*([A-Za-z_]\w*))?\s*(.*?)\bend)?",
    re.IGNORECASE | re.DOTALL,
)
_IF_STMT_RE = re.compile(
    r"\bif\s*\(\s*([^)]+)\s*\)\s*(?!begin\b)([^;]+;)"
    r"(?:\s*else\s*(?!begin\b)([^;]+;))?",
    re.IGNORECASE | re.DOTALL,
)
_BEGIN_END_KW = re.compile(r"\b(begin|end)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _FoldMatch:
    kind: str
    start: int
    end: int
    groups: Tuple[str, ...]

    def group(self, n: int) -> str:
        return self.groups[n - 1] if 0 < n <= len(self.groups) else ""


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


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


def _read_label_after_begin(text: str, i: int) -> Tuple[str, int]:
    i = _skip_ws(text, i)
    if i < len(text) and text[i] == ":":
        i += 1
        m = re.match(_IDENT, text[_skip_ws(text, i) :])
        if m:
            return m.group(0), _skip_ws(text, i) + m.end()
    return "", i


def _find_matching_end(text: str, pos: int) -> int:
    depth = 1
    for m in _BEGIN_END_KW.finditer(text, pos):
        if m.group(1).lower() == "begin":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return m.start()
    return len(text)


def _find_if_begin_block(chunk: str) -> Optional[_FoldMatch]:
    m = re.search(r"\bif\s*\(", chunk, re.IGNORECASE)
    if not m:
        return None
    match_start = m.start()
    paren_start = m.end() - 1
    paren_end = _skip_balanced(chunk, paren_start, "(", ")")
    expr = chunk[paren_start + 1 : paren_end - 1]
    i = _skip_ws(chunk, paren_end)
    bm = re.match(r"\bbegin\b", chunk[i:], re.IGNORECASE)
    if not bm:
        return None
    i += bm.end()
    block_label, i = _read_label_after_begin(chunk, i)
    body_start = _skip_ws(chunk, i)
    end_pos = _find_matching_end(chunk, body_start)
    end_m = re.match(r"\bend\b", chunk[end_pos:], re.IGNORECASE)
    if not end_m:
        return None
    then_body = chunk[body_start:end_pos]
    i = end_pos + end_m.end()

    else_label = ""
    else_body = ""
    i = _skip_ws(chunk, i)
    em = re.match(r"\belse\b", chunk[i:], re.IGNORECASE)
    if em:
        i = _skip_ws(chunk, i + em.end())
        bm2 = re.match(r"\bbegin\b", chunk[i:], re.IGNORECASE)
        if bm2:
            i += bm2.end()
            else_label, i = _read_label_after_begin(chunk, i)
            eb_start = _skip_ws(chunk, i)
            e_end = _find_matching_end(chunk, eb_start)
            else_body = chunk[eb_start:e_end]
            end2 = re.match(r"\bend\b", chunk[e_end:], re.IGNORECASE)
            i = e_end + (end2.end() if end2 else 0)
    return _FoldMatch(
        "if_block",
        match_start,
        i,
        (expr, block_label, then_body, else_label, else_body),
    )


def _subst_index(text: str, var: str, index: int) -> str:
    return re.sub(rf"\b{re.escape(var)}\b", str(index), text)


def _prefix_instance_names(body: str, prefix: str) -> str:
    """Prefix instance leaves in a folded generate fragment (``scope.u_cell``)."""
    if not prefix:
        return body

    def repl(m: re.Match[str]) -> str:
        cell, inst = m.group(1), m.group(2)
        if cell.lower() in _KEYWORDS:
            return m.group(0)
        return f"{cell} {prefix}{inst}"

    return _INSTANCE_PREFIX_RE.sub(repl, body)


def _for_loop_match(chunk: str) -> Optional[re.Match[str]]:
    m = _FOR_RE.search(chunk)
    if m:
        return m
    return _FOR_STMT_RE.search(chunk)


def _unroll_for_loops(
    chunk: str,
    param_map: Mapping[str, str],
    *,
    max_unroll: int = 64,
    scope_prefix: str = "",
) -> str:
    out = chunk
    for _ in range(16):
        m = _for_loop_match(out)
        if not m:
            break
        var, lo_t, cond = m.group(1), m.group(2), m.group(3)
        block_label = ""
        if m.re is _FOR_RE:
            block_label = (m.group(4) or "").strip()
            body = (m.group(5) or "").strip()
        else:
            body = (m.group(4) or "").strip()
        lo = parse_bound_token(lo_t.strip(), param_map)
        if lo is None:
            lo = 0
        hi: Optional[int] = None
        cm = re.match(
            rf"^\s*{re.escape(var)}\s*<\s*(.+?)\s*$",
            cond.strip(),
            re.IGNORECASE,
        )
        if cm:
            hi_t = cm.group(1).strip()
            hi_v = parse_bound_token(hi_t, param_map)
            if hi_v is not None:
                hi = hi_v - 1
        if hi is None:
            break
        if hi < lo:
            lo, hi = hi, lo
        count = hi - lo + 1
        if count > max_unroll:
            break
        parts: List[str] = []
        for i in range(lo, hi + 1):
            part = _subst_index(body, var, i)
            if block_label:
                part = _prefix_instance_names(
                    part, f"{scope_prefix}{block_label}[{i}]."
                )
            elif scope_prefix:
                part = _prefix_instance_names(part, scope_prefix)
            parts.append(part)
        repl = "\n".join(parts)
        out = out[: m.start()] + repl + out[m.end() :]
    return out


def _fold_if_match(
    chunk: str,
    *,
    block_only: bool,
) -> Optional[_FoldMatch | re.Match[str]]:
    m = _find_if_begin_block(chunk)
    if m:
        return m
    if block_only:
        return None
    stmt = _IF_STMT_RE.search(chunk)
    if not stmt:
        return None
    return _FoldMatch(
        "if_stmt",
        stmt.start(),
        stmt.end(),
        (stmt.group(1), "", stmt.group(2), "", stmt.group(3) or ""),
    )


def _fold_if_generate(
    chunk: str,
    param_map: Mapping[str, str],
    *,
    over_approximate: bool = False,
    block_only: bool = False,
    scope_prefix: str = "",
) -> str:
    out = chunk
    for _ in range(16):
        m = _fold_if_match(out, block_only=block_only)
        if not m:
            break
        if m.kind == "if_block":
            expr, block_label, then_body, else_body = (
                m.group(1),
                (m.group(2) or "").strip(),
                m.group(3),
                m.group(5) or "",
            )
        else:
            expr, block_label, then_body, else_body = (
                m.group(1),
                "",
                m.group(3),
                m.group(5) or "",
            )
        truth = expr_is_true(expr, param_map)
        if truth is None:
            if over_approximate:
                repl = else_body if else_body else ""
            else:
                repl = ""
        elif truth:
            child_scope = f"{scope_prefix}{block_label}." if block_label else scope_prefix
            repl = _fold_generate_inner(
                then_body,
                param_map,
                over_approximate_if=over_approximate,
                scope_prefix=child_scope,
            )
        else:
            repl = else_body
        out = out[: m.start] + repl + out[m.end :]
    return out


def _fold_generate_inner(
    inner: str,
    param_map: Mapping[str, str],
    *,
    over_approximate_if: bool = False,
    scope_prefix: str = "",
) -> str:
    for _ in range(16):
        prev = inner
        inner = _fold_if_generate(
            inner,
            param_map,
            over_approximate=over_approximate_if,
            block_only=True,
            scope_prefix=scope_prefix,
        )
        inner = _unroll_for_loops(inner, param_map, scope_prefix=scope_prefix)
        inner = _fold_if_generate(
            inner,
            param_map,
            over_approximate=over_approximate_if,
            block_only=False,
            scope_prefix=scope_prefix,
        )
        if inner == prev:
            break
    return inner


def fold_generate_regions(
    body: str,
    param_map: Mapping[str, str],
    *,
    over_approximate_if: bool = False,
) -> str:
    """Inline generate blocks with literal/param for-loops and folded if-generate."""

    def repl(m: re.Match[str]) -> str:
        return _fold_generate_inner(
            m.group(1),
            param_map,
            over_approximate_if=over_approximate_if,
        )

    return _GEN_BLOCK_RE.sub(repl, body)