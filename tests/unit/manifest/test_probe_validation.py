import pytest

try:
    from rlsmatrix.manifest.validation import validate_probe_sql
except ModuleNotFoundError as exc:
    if exc.name != "pglast":
        raise
    pytest.skip("pglast is not installed in this environment", allow_module_level=True)


def test_allows_single_select() -> None:
    assert validate_probe_sql("SELECT id FROM public.documents;") == "SelectStmt"


def test_allows_single_insert() -> None:
    assert (
        validate_probe_sql("INSERT INTO public.documents(id) VALUES (1) RETURNING id;")
        == "InsertStmt"
    )


def test_allows_single_update_and_delete() -> None:
    assert validate_probe_sql("UPDATE public.documents SET id = 2;") == "UpdateStmt"
    assert validate_probe_sql("DELETE FROM public.documents;") == "DeleteStmt"


def test_rejects_multiple_statements() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        validate_probe_sql("SELECT 1; SELECT 2;")


def test_rejects_ddl() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        validate_probe_sql("DROP TABLE public.documents;")


def test_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_probe_sql("  ")
