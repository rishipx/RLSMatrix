import psycopg
import pytest

from rlsmatrix.core.probes import run_probes
from rlsmatrix.db import sandbox
from rlsmatrix.db.bootstrap import apply_bootstrap_sql
from rlsmatrix.db.connection import connection_info
from rlsmatrix.db.sandbox import (
    connect_maintenance,
    create_database,
    drop_database,
    drop_roles,
    list_roles,
)
from rlsmatrix.examples import DIRECTORY as EXAMPLES
from rlsmatrix.manifest import load_test_suite

pytestmark = pytest.mark.integration


def _exists(name: str) -> bool:
    with psycopg.connect(connection_info(), autocommit=True) as connection:
        row = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
    return row is not None


def test_one_admin_connection_can_create_and_drop_several_databases() -> None:
    with connect_maintenance() as admin:
        databases = [create_database(admin=admin) for _ in range(3)]
        assert all(_exists(item.name) for item in databases)
        for item in databases:
            drop_database(item.name, admin=admin)
    assert not any(_exists(item.name) for item in databases)


def test_a_lost_admin_connection_falls_back_to_a_fresh_one() -> None:
    admin = connect_maintenance()
    database = create_database(admin=admin)
    admin.close()
    drop_database(database.name, admin=admin)
    assert not _exists(database.name)
    replacement = create_database(admin=admin)
    try:
        assert _exists(replacement.name)
    finally:
        drop_database(replacement.name)


def test_a_lingering_session_does_not_block_the_drop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox, "_SESSION_WAIT_SECONDS", 0.05)
    database = create_database()
    with psycopg.connect(database.conninfo, autocommit=True) as lingering:
        lingering.execute("SELECT 1")
        drop_database(database.name)
    assert not _exists(database.name)


def test_dropping_a_missing_database_is_not_an_error() -> None:
    database = create_database()
    drop_database(database.name)
    drop_database(database.name)


def test_probes_share_a_connection_and_survive_losing_it() -> None:
    folder = EXAMPLES / "tenant_isolation"
    suite = load_test_suite((folder / "suite.yaml").read_text("utf-8"))
    before = list_roles()
    template = create_database()
    try:
        apply_bootstrap_sql(
            template.conninfo, (folder / "schema.sql").read_text("utf-8")
        )
        expected = [p.passed for p in run_probes(template.conninfo, suite)]
        assert all(expected)

        with psycopg.connect(template.conninfo, autocommit=True) as shared:
            assert [p.passed for p in run_probes(template.conninfo, suite, shared)] == (
                expected
            )
            assert not shared.closed

        lost = psycopg.connect(template.conninfo, autocommit=True)
        lost.close()
        recovered = run_probes(template.conninfo, suite, lost)
        assert [p.passed for p in recovered] == expected
    finally:
        drop_database(template.name)
        drop_roles(list_roles() - before)
