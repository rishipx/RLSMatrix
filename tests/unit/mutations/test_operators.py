import pytest

from rlsmatrix.mutations import generate_mutations
from rlsmatrix.mutations.operators import (
    CORE_OPERATORS,
    OPERATORS,
    SURVIVOR_HINTS,
    validate_operators,
)

POLICY = {
    "schemaname": "public",
    "tablename": "docs",
    "policyname": "owner_only",
    "roles": ["authenticated"],
    "cmd": "ALL",
    "qual": "(owner_id = auth.uid())",
    "with_check": "(owner_id = auth.uid())",
}


def test_every_operator_has_a_survivor_hint() -> None:
    assert set(SURVIVOR_HINTS) == set(OPERATORS)


def test_drop_policy_is_generated_for_every_policy() -> None:
    mutations = generate_mutations([POLICY], [], {"DROP_POLICY"})
    assert [m.sql for m in mutations] == ['DROP POLICY "owner_only" ON "public"."docs"']
    assert "positive probe" not in mutations[0].hint  # hint text is about the access
    assert "allowed" in mutations[0].hint


def test_operator_selection_filters_output() -> None:
    kinds = {m.kind for m in generate_mutations([POLICY], [], {"OPEN_USING"})}
    assert kinds == {"OPEN_USING"}


def test_operator_names_are_case_insensitive() -> None:
    assert validate_operators(["open_using", " Disable_RLS "]) == {
        "OPEN_USING",
        "DISABLE_RLS",
    }


def test_unknown_or_empty_operator_selection_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown mutation operator"):
        validate_operators(["NOPE"])
    with pytest.raises(ValueError, match="at least one"):
        validate_operators([])


def test_mutation_ids_are_unique_and_deterministic() -> None:
    first = generate_mutations([POLICY], [])
    second = generate_mutations([POLICY], [])
    assert [m.id for m in first] == [m.id for m in second]
    assert len({m.id for m in first}) == len(first)


def test_survivor_hint_is_exposed_on_the_mutation() -> None:
    mutation = generate_mutations([POLICY], [], {"OPEN_USING"})[0]
    assert "must be denied" in mutation.hint


def test_default_selection_is_the_core_group() -> None:
    assert validate_operators(None) == CORE_OPERATORS
    assert len(CORE_OPERATORS) == 5


def test_group_names_select_whole_groups() -> None:
    predicate = validate_operators(["predicate"])
    assert predicate == {"FLIP_COMPARISON", "SWAP_BOOL_OP", "DROP_CLAUSE"}
    assert validate_operators(["ALL"]) == set(OPERATORS)
    assert validate_operators(["core", "drop_clause"]) == CORE_OPERATORS | {
        "DROP_CLAUSE"
    }


def test_predicate_operators_are_opt_in() -> None:
    policy = {
        **POLICY,
        "qual": "(a = 1 AND b = 2)",
        "with_check": None,
        "cmd": "SELECT",
    }
    assert {m.kind for m in generate_mutations([policy], [])}.isdisjoint(
        {"FLIP_COMPARISON", "SWAP_BOOL_OP", "DROP_CLAUSE"}
    )
    kinds = {m.kind for m in generate_mutations([policy], [], {"FLIP_COMPARISON"})}
    assert kinds == {"FLIP_COMPARISON"}


def test_shape_group_and_all_group() -> None:
    assert validate_operators(["shape"]) == {
        "RESTRICTIVE_TO_PERMISSIVE",
        "WIDEN_COMMAND",
        "NO_FORCE_RLS",
    }
    assert len(OPERATORS) == 11
    assert validate_operators(["all"]) == set(OPERATORS)
