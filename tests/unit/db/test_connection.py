from typing import Any

import pytest

from rlsmatrix.db import connection as connection_module
from rlsmatrix.db.connection import Session


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[FakeConnection]:
    created: list[FakeConnection] = []

    def connect(conninfo: str, **kwargs: Any) -> FakeConnection:
        assert kwargs == {"autocommit": True}
        created.append(FakeConnection())
        return created[-1]

    monkeypatch.setattr(connection_module.psycopg, "connect", connect)
    return created


def test_opens_one_connection_lazily_and_closes_it(
    opened: list[FakeConnection],
) -> None:
    with Session("dsn") as session:
        assert opened == []
        first = session.connection
        assert session.connection is first
    assert len(opened) == 1 and opened[0].closed


def test_reuses_a_given_connection_and_leaves_it_open(
    opened: list[FakeConnection],
) -> None:
    given = FakeConnection()
    with Session("dsn", given) as session:  # type: ignore[arg-type]
        assert session.connection is given
    assert not given.closed and opened == []


def test_reconnects_after_the_connection_is_lost(
    opened: list[FakeConnection],
) -> None:
    given = FakeConnection()
    with Session("dsn", given) as session:  # type: ignore[arg-type]
        given.closed = True
        replacement = session.connection
        assert replacement is opened[0] and replacement is not given
    assert replacement.closed and given.close_calls == 0
