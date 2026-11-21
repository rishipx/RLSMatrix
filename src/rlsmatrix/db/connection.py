"""Connection strings and a connection wrapper that survives a lost session."""

from __future__ import annotations

from types import TracebackType
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

from rlsmatrix.config import get_settings

MIN_PASSWORD_LENGTH = 24
PLACEHOLDER_PASSWORDS = frozenset({"change_me", "changeme"})


def connection_info(database: str | None = None) -> str:
    settings = get_settings()
    password = settings.database_password
    if (
        len(password) < MIN_PASSWORD_LENGTH
        or password.casefold() in PLACEHOLDER_PASSWORDS
    ):
        raise RuntimeError(
            f"Set RLSMATRIX_DB_PASSWORD to a unique value of at least "
            f"{MIN_PASSWORD_LENGTH} characters in the local .env file "
            "(for example, secrets.token_urlsafe(32))."
        )
    return make_conninfo(
        host=settings.database_host,
        port=settings.database_port,
        dbname=database or settings.database_name,
        user=settings.database_user,
        password=password,
        connect_timeout=settings.connect_timeout_seconds,
        application_name="rlsmatrix-local-sandbox",
    )


class Session:
    """An autocommit connection that reconnects if it was lost.

    A dropped connection must not cascade into every later statement. Pass an
    existing ``connection`` to reuse it; the session then closes only the
    connections it opened itself.
    """

    def __init__(
        self, conninfo: str, connection: psycopg.Connection[Any] | None = None
    ) -> None:
        self._conninfo = conninfo
        self._connection = connection
        self._owned = connection is None

    @property
    def connection(self) -> psycopg.Connection[Any]:
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(self._conninfo, autocommit=True)
            self._owned = True
        return self._connection

    def close(self) -> None:
        if self._owned and self._connection is not None:
            self._connection.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
