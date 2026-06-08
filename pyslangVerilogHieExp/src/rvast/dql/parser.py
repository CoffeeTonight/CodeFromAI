"""
parser.py - Lark-based DQL parser for JIRA-JQL style queries.
Transforms source -> AST nodes.
This is the foundation to match JS parseDQL / evaluateDQL exactly.
"""

from dataclasses import dataclass, field as dc_field
from typing import List, Union, Optional, Any
from pathlib import Path
from lark import Lark, Transformer, v_args, Token, Tree

# AST node definitions (simple, explicit for evaluator)

@dataclass
class DQLQuery:
    """Root wrapper"""
    expr: 'Expr'

@dataclass
class And:
    left: 'Expr'
    right: 'Expr'

@dataclass
class Or:
    left: 'Expr'
    right: 'Expr'

@dataclass
class Not:
    expr: 'Expr'

@dataclass
class Comparison:
    """field op value   e.g. module ~ "uart*" """
    field: str
    op: str          # '=', '!=', '~', '!~'
    value: str

@dataclass
class InExpr:
    """field in ("a", "b")"""
    field: str
    values: List[str]
    negated: bool = False   # for NOT IN

# Union type for expressions
Expr = Union[And, Or, Not, Comparison, InExpr, 'BarePattern']

@dataclass
class BarePattern:
    """Bare word or pattern without explicit field, e.g. uart*  => treated as module ~ pattern"""
    pattern: str
    default_field: str = "module"

# Type alias for clarity
DQLAst = DQLQuery


_GRAMMAR_PATH = Path(__file__).parent / "dql_grammar.lark"

# Global parser instance (lazy)
_lark_parser: Optional[Lark] = None


def get_parser() -> Lark:
    global _lark_parser
    if _lark_parser is None:
        grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
        # Use LALR for speed, or Earley if needed for ambiguity (we keep unambiguous)
        _lark_parser = Lark(
            grammar,
            parser="lalr",
            start="start",
            propagate_positions=True,
            maybe_placeholders=False,
        )
    return _lark_parser


class DQLTransformer(Transformer):
    """Transform Lark parse tree into our clean AST dataclasses.
    WORD is used for both field names and bare patterns / values.
    We normalize here.
    """

    # Known fields for validation / normalization
    KNOWN_FIELDS = {"module", "port", "name", "file", "hierarchy"}

    def start(self, items):
        return DQLQuery(expr=items[0])

    def expr(self, items):
        return items[0]

    def or_term(self, items):
        operands = [x for x in items if not isinstance(x, Token)]
        if len(operands) == 1:
            return operands[0]
        node = operands[0]
        for r in operands[1:]:
            node = Or(left=node, right=r)
        return node

    def and_term(self, items):
        operands = [x for x in items if not isinstance(x, Token)]
        if len(operands) == 1:
            return operands[0]
        node = operands[0]
        for r in operands[1:]:
            node = And(left=node, right=r)
        return node

    def not_term(self, items):
        # non-NOT alternative: just pass atom through
        return items[0]

    def not_atom(self, items):
        # "NOT"i atom  -> Not(...)
        return Not(expr=items[0])

    def atom(self, items):
        return items[0]

    # New rule names from grammar
    def field_op(self, items):
        # [WORD, OP, value]
        f = self._norm_field(items[0])
        op = self._norm_op(items[1])
        v = self._norm_value(items[2])
        return Comparison(field=f, op=op, value=v)

    def field_in(self, items):
        f = self._norm_field(items[0])
        vals = items[-1]
        return InExpr(field=f, values=vals, negated=False)

    def field_not_in(self, items):
        f = self._norm_field(items[0])
        vals = items[-1]
        return InExpr(field=f, values=vals, negated=True)

    def value_list(self, items):
        return [self._norm_value(v) for v in items if not isinstance(v, Token)]

    def value(self, items):
        return items[0]

    def STRING(self, tok: Token):
        s = tok.value
        if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
            s = s[1:-1]
        return s.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")

    def WORD(self, tok: Token):
        return tok.value

    def bare(self, items):
        p = items[0] if items else ""
        if isinstance(p, Token):
            p = p.value
        return BarePattern(pattern=str(p))

    # Symbol terminals
    def EQ(self, _): return "="
    def NE(self, _): return "!="
    def TILDE(self, _): return "~"
    def NOT_TILDE(self, _): return "!~"

    # Helpers
    def _norm_field(self, f: Any) -> str:
        if isinstance(f, Token):
            name = f.value.lower()
        else:
            name = str(f).lower()
        # Accept known fields; for bare patterns used as field we will validate in evaluator or here
        return name

    def _norm_op(self, op: Any) -> str:
        if isinstance(op, Token):
            return op.value
        return "=" if op is None else str(op)

    def _norm_value(self, v: Any) -> str:
        if isinstance(v, (Token, str)):
            return str(v)
        return str(v)


def parse_dql(query: str) -> DQLQuery:
    """
    Public entry: parse DQL string into AST.
    Goal: structural and token-level equivalence to the JS parseDQL in hierarchy_explorer.html.
    This function is now the primary focus for achieving JS-level parity.
    """
    if not query or not query.strip():
        # Empty query → match everything (consistent with observed HTML behavior)
        return DQLQuery(expr=Comparison(field="module", op="~", value="*"))

    parser = get_parser()
    try:
        tree = parser.parse(query)
        ast = DQLTransformer().transform(tree)
        return ast
    except Exception as e:
        # Produce errors that are as close as possible to what the JS parser would surface
        msg = str(e)
        if "Unexpected token" in msg or "Unexpected character" in msg:
            msg = "Syntax error: " + msg.split("at line")[0].strip()
        raise RuntimeError(f"Parse error: {msg}") from e


def ast_to_dict(node: Any) -> Any:
    """Debug helper: convert AST to nested dict for printing."""
    if isinstance(node, And):
        return {"AND": [ast_to_dict(node.left), ast_to_dict(node.right)]}
    if isinstance(node, Or):
        return {"OR": [ast_to_dict(node.left), ast_to_dict(node.right)]}
    if isinstance(node, Not):
        return {"NOT": ast_to_dict(node.expr)}
    if isinstance(node, Comparison):
        return f"{node.field} {node.op} {node.value!r}"
    if isinstance(node, InExpr):
        neg = "NOT " if node.negated else ""
        return f"{node.field} {neg}IN ({', '.join(repr(v) for v in node.values)})"
    if isinstance(node, DQLQuery):
        return ast_to_dict(node.expr)
    if isinstance(node, BarePattern):
        return f"bare:{node.pattern!r} (default module ~)"
    return str(node)


if __name__ == "__main__":
    # Quick smoke tests for grammar
    tests = [
        'module ~ "uart"',
        'module !~ "foo"',
        'port in ("clk", "reset")',
        'name ~ "u_cpu*" AND port ~ "irq*"',
        'NOT module = "glitch"',
        '(module ~ "uart" OR module ~ "spi") AND NOT file ~ "*tb*"',
        'module in ("uart", "spi", "i2c")',
        '((A AND (B OR C)) AND NOT D)',   # will fail currently because A/B are bare - we will support bare soon
    ]
    for q in tests:
        try:
            a = parse_dql(q)
            print("OK :", q)
            print("   ", ast_to_dict(a))
        except Exception as e:
            print("FAIL:", q, "->", e)
        print()
