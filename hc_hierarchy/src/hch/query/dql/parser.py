"""Lark DQL parser → AST (hc_hierarchy)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Union

from lark import Lark, Token, Transformer

_GRAMMAR = Path(__file__).parent / "dql_grammar.lark"
_lark_parser: Optional[Lark] = None


@dataclass
class DQLQuery:
    expr: "Expr"


@dataclass
class And:
    left: "Expr"
    right: "Expr"


@dataclass
class Or:
    left: "Expr"
    right: "Expr"


@dataclass
class Not:
    expr: "Expr"


@dataclass
class Comparison:
    field: str
    op: str
    value: str


@dataclass
class InExpr:
    field: str
    values: List[str]
    negated: bool = False


@dataclass
class BarePattern:
    pattern: str
    default_field: str = "inst"


Expr = Union[And, Or, Not, Comparison, InExpr, BarePattern]


def get_parser() -> Lark:
    global _lark_parser
    if _lark_parser is None:
        _lark_parser = Lark(
            _GRAMMAR.read_text(encoding="utf-8"),
            parser="lalr",
            start="start",
        )
    return _lark_parser


class DQLTransformer(Transformer):
    def start(self, items):
        return DQLQuery(expr=items[0])

    def expr(self, items):
        return items[0]

    def or_term(self, items):
        ops = [x for x in items if not isinstance(x, Token)]
        node = ops[0]
        for r in ops[1:]:
            node = Or(left=node, right=r)
        return node

    def and_term(self, items):
        ops = [x for x in items if not isinstance(x, Token)]
        node = ops[0]
        for r in ops[1:]:
            node = And(left=node, right=r)
        return node

    def not_atom(self, items):
        return Not(expr=items[0])

    def not_term(self, items):
        return items[0]

    def atom(self, items):
        return items[0]

    def comparison_op(self, items):
        return items[0]

    def field_op(self, items):
        f = str(items[0]).lower()
        op = items[1] if isinstance(items[1], str) else str(items[1])
        v = items[2]
        return Comparison(field=f, op=op, value=str(v))

    def field_in(self, items):
        return InExpr(field=str(items[0]).lower(), values=items[-1], negated=False)

    def field_not_in(self, items):
        return InExpr(field=str(items[0]).lower(), values=items[-1], negated=True)

    def value_list(self, items):
        return [str(v) for v in items if not isinstance(v, Token)]

    def value(self, items):
        return items[0]

    def bare(self, items):
        p = items[0]
        return BarePattern(pattern=str(p))

    def STRING(self, tok: Token):
        s = tok.value
        if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
            s = s[1:-1]
        return s.replace('\\"', '"').replace("\\'", "'")

    def WORD(self, tok: Token):
        return tok.value

    def EQ2(self, _):
        return "="

    def EQ(self, _):
        return "="

    def NE(self, _):
        return "!="

    def TILDE(self, _):
        return "~"

    def NOT_TILDE(self, _):
        return "!~"

    def PREFIX(self, _):
        return "^="

    def GE(self, _):
        return ">="

    def LE(self, _):
        return "<="

    def GT(self, _):
        return ">"

    def LT(self, _):
        return "<"

    def NUM(self, tok: Token):
        return tok.value


def parse_dql(query: str) -> DQLQuery:
    q = (query or "").strip()
    if not q:
        return DQLQuery(expr=Comparison(field="inst", op="~", value="*"))
    tree = get_parser().parse(q)
    return DQLTransformer().transform(tree)