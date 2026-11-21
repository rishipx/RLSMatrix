"""Fine-grained mutations of a policy predicate.

``OPEN_USING`` replaces a whole predicate with ``true``, which is easy to catch.
A realistic mistake is smaller: a flipped comparison, an ``AND`` that should
have been an ``OR``, or a forgotten clause. This module parses the predicate
with PostgreSQL's own parser (via pglast), changes one small thing at a time,
and prints the result back as SQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pglast import ast, enums, parse_sql
from pglast.parser import ParseError
from pglast.stream import RawStream

FLIP_COMPARISON = "FLIP_COMPARISON"
SWAP_BOOL_OP = "SWAP_BOOL_OP"
DROP_CLAUSE = "DROP_CLAUSE"

PREDICATE_OPERATORS = frozenset({FLIP_COMPARISON, SWAP_BOOL_OP, DROP_CLAUSE})

_COMPARISON_FLIPS = {
    "=": "<>",
    "<>": "=",
    "!=": "=",
    "<": ">=",
    ">=": "<",
    ">": "<=",
    "<=": ">",
}
_SNIPPET_LENGTH = 60


@dataclass(frozen=True, slots=True)
class PredicateVariant:
    """One mutated copy of a predicate."""

    kind: str
    site: str  # stable discriminator, used to build deterministic mutation ids
    description: str
    expression: str


def _snippet(node: Any) -> str:
    text = " ".join(RawStream()(node).split())
    if len(text) > _SNIPPET_LENGTH:
        text = text[: _SNIPPET_LENGTH - 1] + "…"
    return text


def _parse(expression: str) -> ast.ResTarget | None:
    """Parse a predicate as the only column of ``SELECT <predicate>``."""
    try:
        statements = parse_sql(f"SELECT {expression}")
    except ParseError:
        return None
    if len(statements) != 1:
        return None
    statement = statements[0].stmt
    targets = getattr(statement, "targetList", None)
    if (
        not isinstance(statement, ast.SelectStmt)
        or statement.fromClause
        or statement.whereClause
        or not targets
        or len(targets) != 1
    ):
        return None
    return targets[0]


def _nodes(value: Any) -> Iterator[Any]:
    """Every AST node below ``value``, parents before children."""
    if isinstance(value, ast.Node):
        yield value
        for attribute in value.__slots__:
            yield from _nodes(getattr(value, attribute, None))
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _nodes(item)


def _operator_name(node: ast.A_Expr) -> str | None:
    if node.kind != enums.A_Expr_Kind.AEXPR_OP or not node.name or len(node.name) != 1:
        return None
    name = getattr(node.name[0], "sval", None)
    return name if isinstance(name, str) else None


def _flip_sites(root: Any) -> list[Any]:
    sites = []
    for node in _nodes(root):
        if isinstance(node, ast.NullTest) or (
            isinstance(node, ast.A_Expr)
            and node.lexpr is not None
            and node.rexpr is not None
            and _operator_name(node) in _COMPARISON_FLIPS
        ):
            sites.append(node)
    return sites


def _bool_sites(root: Any) -> list[ast.BoolExpr]:
    return [
        node
        for node in _nodes(root)
        if isinstance(node, ast.BoolExpr)
        and node.boolop in (enums.BoolExprType.AND_EXPR, enums.BoolExprType.OR_EXPR)
        and len(node.args) >= 2
    ]


def _clause_sites(root: Any) -> list[tuple[int, int]]:
    """``(chain index, clause index)`` for every clause of every AND/OR chain."""
    return [
        (chain, clause)
        for chain, node in enumerate(_bool_sites(root))
        for clause in range(len(node.args))
    ]


def _joiner(node: ast.BoolExpr) -> str:
    return "AND" if node.boolop == enums.BoolExprType.AND_EXPR else "OR"


def _flip(node: Any) -> tuple[str, str]:
    """Flip one comparison or NULL test in place; return (old, new) symbols."""
    if isinstance(node, ast.NullTest):
        if node.nulltesttype == enums.NullTestType.IS_NULL:
            node.nulltesttype = enums.NullTestType.IS_NOT_NULL
            return "IS NULL", "IS NOT NULL"
        node.nulltesttype = enums.NullTestType.IS_NULL
        return "IS NOT NULL", "IS NULL"
    old = _operator_name(node) or ""
    new = _COMPARISON_FLIPS[old]
    node.name = (ast.String(sval=new),)
    return old, new


def _variants(
    expression: str,
    kind: str,
    sites: Any,
    mutate: Any,
) -> Iterator[PredicateVariant]:
    """Re-parse the predicate once per site, mutate that site, print it back."""
    original = _parse(expression)
    if original is None:
        return
    unchanged = RawStream()(original.val)
    for index, site in enumerate(sites(original.val)):
        target = _parse(expression)
        if target is None:  # pragma: no cover - the same text parsed above
            return
        description = mutate(target.val, site)
        text = RawStream()(target.val)
        if text == unchanged or _parse(text) is None:
            continue
        yield PredicateVariant(kind, f"{kind.lower()}:{index}", description, text)


def predicate_variants(
    expression: str, operators: frozenset[str] | set[str]
) -> list[PredicateVariant]:
    """Mutated copies of ``expression`` for the selected predicate operators.

    The result is deterministic and free of duplicates. A predicate that cannot
    be parsed yields nothing instead of raising, so one unusual policy does not
    stop a campaign.
    """
    found: list[PredicateVariant] = []

    if FLIP_COMPARISON in operators:

        def flip_sites(root: Any) -> list[int]:
            return list(range(len(_flip_sites(root))))

        def flip(root: Any, index: int) -> str:
            node = _flip_sites(root)[index]
            context = _snippet(node)
            old, new = _flip(node)
            return f"Flip {old} to {new} in `{context}`."

        found.extend(_variants(expression, FLIP_COMPARISON, flip_sites, flip))

    if SWAP_BOOL_OP in operators:

        def swap_sites(root: Any) -> list[int]:
            return list(range(len(_bool_sites(root))))

        def swap(root: Any, index: int) -> str:
            node = _bool_sites(root)[index]
            context = _snippet(node)
            old = _joiner(node)
            node.boolop = (
                enums.BoolExprType.OR_EXPR
                if old == "AND"
                else enums.BoolExprType.AND_EXPR
            )
            new = "OR" if old == "AND" else "AND"
            return f"Swap {old} for {new} in `{context}`."

        found.extend(_variants(expression, SWAP_BOOL_OP, swap_sites, swap))

    if DROP_CLAUSE in operators:

        def drop_sites(root: Any) -> list[tuple[int, int]]:
            return _clause_sites(root)

        def drop(root: Any, site: tuple[int, int]) -> str:
            chain, clause = site
            node = _bool_sites(root)[chain]
            removed = _snippet(node.args[clause])
            joiner = _joiner(node)
            node.args = tuple(
                item for position, item in enumerate(node.args) if position != clause
            )
            return f"Remove `{removed}` from an {joiner} chain."

        found.extend(_variants(expression, DROP_CLAUSE, drop_sites, drop))

    unique: dict[tuple[str, str], PredicateVariant] = {}
    for variant in found:
        unique.setdefault((variant.kind, variant.expression), variant)
    return list(unique.values())
