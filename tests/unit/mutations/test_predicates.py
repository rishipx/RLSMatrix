import pytest

from rlsmatrix.mutations.predicates import (
    DROP_CLAUSE,
    FLIP_COMPARISON,
    PREDICATE_OPERATORS,
    SWAP_BOOL_OP,
    predicate_variants,
)

OWNER_OR_SHARED = "((owner_id = auth.uid()) OR shared) AND (NOT archived)"
MEMBER = (
    "(EXISTS ( SELECT 1 FROM members m "
    "WHERE ((m.user_id = auth.uid()) AND (m.org_id = docs.org_id))))"
)


def _expressions(expression: str, operator: str) -> list[str]:
    return [v.expression for v in predicate_variants(expression, {operator})]


def test_flips_each_comparison_once() -> None:
    result = _expressions("a = 1 AND b < 2", FLIP_COMPARISON)
    assert result == ["a <> 1 AND b < 2", "a = 1 AND b >= 2"]


def test_flips_null_tests() -> None:
    assert _expressions("owner_id IS NOT NULL", FLIP_COMPARISON) == ["owner_id IS NULL"]
    assert _expressions("owner_id IS NULL", FLIP_COMPARISON) == ["owner_id IS NOT NULL"]


def test_swaps_each_boolean_operator_once() -> None:
    result = _expressions(OWNER_OR_SHARED, SWAP_BOOL_OP)
    assert len(result) == 2
    assert any("owner_id = auth.uid() AND shared" in text for text in result)
    assert any(" OR NOT archived" in text for text in result)


def test_drops_each_clause_and_keeps_precedence() -> None:
    result = _expressions(OWNER_OR_SHARED, DROP_CLAUSE)
    assert len(result) == 4
    # Dropping `NOT archived` leaves the inner OR, which must stay grouped.
    assert any("NOT archived" not in text and "OR shared" in text for text in result)
    # Dropping `shared` leaves the owner check and the archived check.
    assert "(owner_id = auth.uid()) AND NOT archived" in result


def test_mutates_inside_subqueries() -> None:
    result = _expressions(MEMBER, DROP_CLAUSE)
    assert len(result) == 2
    assert all(text.startswith("EXISTS (SELECT 1 FROM members") for text in result)
    assert any("m.org_id = docs.org_id" not in text for text in result)


def test_variants_are_deterministic_and_unique() -> None:
    first = predicate_variants(OWNER_OR_SHARED, PREDICATE_OPERATORS)
    second = predicate_variants(OWNER_OR_SHARED, PREDICATE_OPERATORS)
    assert first == second
    assert len({(v.kind, v.expression) for v in first}) == len(first)
    assert len({v.site for v in first}) == len(first)


def test_operators_not_selected_produce_nothing() -> None:
    assert predicate_variants("a = 1", set()) == []
    assert predicate_variants("a = 1", {DROP_CLAUSE}) == []  # no chain to shorten


@pytest.mark.parametrize(
    "expression", ["true", "auth.uid()", "((", "1; DROP TABLE x", "a, b", ""]
)
def test_unusable_predicates_yield_nothing(expression: str) -> None:
    assert predicate_variants(expression, PREDICATE_OPERATORS) == []


def test_every_variant_is_valid_sql_that_differs_from_the_original() -> None:
    from rlsmatrix.mutations.predicates import _parse

    for variant in predicate_variants(
        OWNER_OR_SHARED + " AND x IS NULL", PREDICATE_OPERATORS
    ):
        assert _parse(variant.expression) is not None
        assert variant.description
