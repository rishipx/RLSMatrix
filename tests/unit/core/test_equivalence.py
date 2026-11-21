import psycopg
from psycopg import errors

from rlsmatrix.core.equivalence import (
    Observation,
    TableSample,
    _battery,
    _classify_error,
    describe_difference,
)


def _sample(rows: list[dict] | None = None) -> TableSample:
    rows = (
        rows if rows is not None else [{"id": 1, "owner": "a"}, {"id": 2, "owner": "b"}]
    )
    return TableSample("public", "docs", ["id", "owner"], rows)


def _obs(signature: str, summary: str = "s", actor: str = "alice") -> Observation:
    return Observation(actor, "public.docs", "SELECT all rows", signature, summary)


def test_identical_fingerprints_have_no_difference() -> None:
    reference = {"k": _obs("1"), "j": _obs("2")}
    assert describe_difference(reference, dict(reference)) is None


def test_difference_names_the_actor_table_and_both_outcomes() -> None:
    reference = {"k": _obs("1", "1 row(s) visible")}
    observed = {"k": _obs("2", "2 row(s) visible")}
    text = describe_difference(reference, observed)
    assert text is not None
    assert "As alice, SELECT all rows on public.docs" in text
    assert "1 row(s) visible before the change, 2 row(s) visible after it" in text


def test_additional_differences_are_counted() -> None:
    reference = {"a": _obs("1"), "b": _obs("1"), "c": _obs("1")}
    observed = {"a": _obs("2"), "b": _obs("2"), "c": _obs("1")}
    assert "1 more behaviour change(s)" in (
        describe_difference(reference, observed) or ""
    )


def test_observations_missing_from_one_side_are_ignored() -> None:
    assert describe_difference({"a": _obs("1")}, {}) is None


def test_distinct_values_are_unique_ordered_and_skip_nulls() -> None:
    sample = _sample(
        [{"id": 1, "owner": None}, {"id": 2, "owner": "x"}, {"id": 3, "owner": "x"}]
    )
    assert sample.distinct_values("owner") == ["x"]
    many = _sample([{"id": n, "owner": "o"} for n in range(10)])
    assert many.distinct_values("id") == [0, 1, 2]


def test_battery_covers_reads_deletes_updates_and_inserts() -> None:
    keys = [key for key, *_ in _battery(_sample())]
    assert keys[:3] == ["select", "delete", "update-all"]
    assert "update id=1" in keys and 'update owner="a"' in keys
    assert keys[-2:] == ["insert row 0", "insert row 1"]


def test_battery_for_an_empty_table_has_no_inserts_or_column_updates() -> None:
    keys = [key for key, *_ in _battery(_sample([]))]
    assert keys == ["select", "delete", "update-all"]


def test_error_classes() -> None:
    rls = errors.InsufficientPrivilege(
        'new row violates row-level security policy for table "docs"'
    )
    assert _classify_error(rls)[0] == "rls"
    assert (
        _classify_error(errors.InsufficientPrivilege("permission denied"))[0]
        == "denied"
    )
    assert _classify_error(errors.UniqueViolation("duplicate key"))[0] == "allowed"
    assert _classify_error(psycopg.errors.SyntaxError("boom"))[0].startswith("error:")
