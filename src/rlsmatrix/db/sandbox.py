"""Disposable databases, roles and the campaign lock of the sandbox server."""

from __future__ import annotations

import re
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any, NamedTuple

import psycopg
from psycopg import sql

from rlsmatrix.config import get_settings
from rlsmatrix.db.connection import connection_info

SANDBOX_DB_PATTERN = re.compile(r"rlsmatrix_[a-f0-9]{12}")

# Arbitrary constant that identifies the campaign lock inside PostgreSQL.
CAMPAIGN_LOCK_KEY = 0x524C534D  # "RLSM"


class CampaignBusyError(RuntimeError):
    """Raised when another campaign is already running against this sandbox."""


class Database(NamedTuple):
    name: str
    conninfo: str


def _require_sandbox_name(name: str) -> None:
    if SANDBOX_DB_PATTERN.fullmatch(name) is None:
        raise ValueError("Refusing to use a database outside the RLSMatrix namespace.")


@contextmanager
def campaign_lock() -> Iterator[None]:
    """Allow one campaign at a time across every process using this sandbox.

    Roles are shared by every database in the cluster, so two campaigns running
    together would drop each other's roles. The lock is a PostgreSQL advisory
    lock held on a dedicated connection. It covers the CLI and the web app
    alike, and PostgreSQL releases it if the process dies.
    """
    with psycopg.connect(connection_info(), autocommit=True) as connection:
        row = connection.execute(
            "SELECT pg_try_advisory_lock(%s)", (CAMPAIGN_LOCK_KEY,)
        ).fetchone()
        if row is None or not row[0]:
            raise CampaignBusyError(
                "Another campaign is already running. Wait for it to finish."
            )
        try:
            yield
        finally:
            # Closing the connection releases the lock anyway, so a failure here
            # must not hide the error that ended the campaign.
            with suppress(psycopg.Error):
                connection.execute(
                    "SELECT pg_advisory_unlock(%s)", (CAMPAIGN_LOCK_KEY,)
                )


def connect_maintenance() -> psycopg.Connection[Any]:
    """Open an autocommit connection to the maintenance database."""
    return psycopg.connect(connection_info(), autocommit=True)


def _execute_maintenance(
    statement: sql.SQL | sql.Composed, admin: psycopg.Connection[Any] | None
) -> None:
    """Run ``statement`` on ``admin``, or on a short-lived connection.

    The short-lived connection is used when no ``admin`` was given and also
    when the one given was lost, so a dropped connection cannot leave a
    database behind.
    """
    if admin is not None and not admin.closed:
        try:
            admin.execute(statement)
            return
        except psycopg.OperationalError:
            if not admin.closed:
                raise  # a server error, not a lost connection
    with connect_maintenance() as connection:
        connection.execute(statement)


def create_database(
    template: str | None = None, *, admin: psycopg.Connection[Any] | None = None
) -> Database:
    """Create a uniquely named database, optionally cloned from ``template``."""
    name = f"rlsmatrix_{secrets.token_hex(6)}"
    if template is None:
        statement = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
    else:
        _require_sandbox_name(template)
        statement = sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
            sql.Identifier(name), sql.Identifier(template)
        )
    _execute_maintenance(statement, admin)
    return Database(name, connection_info(name))


_SESSION_POLL_SECONDS = 0.002
_SESSION_WAIT_SECONDS = 2.0


def _wait_for_sessions_to_end(name: str, admin: psycopg.Connection[Any]) -> None:
    """Wait briefly until no session is connected to ``name``.

    ``DROP DATABASE`` re-checks for other sessions only every 100 ms, so
    dropping right after a session closed can cost a whole interval while that
    backend exits. Polling every few milliseconds avoids it. If a session
    lingers, ``DROP DATABASE ... WITH (FORCE)`` still removes it.
    """
    deadline = time.monotonic() + _SESSION_WAIT_SECONDS
    while time.monotonic() < deadline:
        found = admin.execute(
            "SELECT 1 FROM pg_stat_activity WHERE datname = %s LIMIT 1", (name,)
        ).fetchone()
        if found is None:
            return
        time.sleep(_SESSION_POLL_SECONDS)


def drop_database(name: str, *, admin: psycopg.Connection[Any] | None = None) -> None:
    _require_sandbox_name(name)
    if admin is not None and not admin.closed:
        with suppress(psycopg.Error):  # the drop below reports a real problem
            _wait_for_sessions_to_end(name, admin)
    _execute_maintenance(
        sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)),
        admin,
    )


def list_roles() -> set[str]:
    with psycopg.connect(connection_info(), autocommit=True) as connection:
        rows = connection.execute(
            "SELECT rolname FROM pg_roles WHERE rolname !~ '^pg_'"
        ).fetchall()
    return {row[0] for row in rows}


def drop_roles(role_names: set[str]) -> list[str]:
    """Drop roles; return the names that could not be dropped.

    Roles belong to the cluster, not to a database, so they outlive the
    databases a campaign creates and must be removed separately.
    """
    protected = {get_settings().database_user}
    failed: list[str] = []
    with psycopg.connect(connection_info(), autocommit=True) as connection:
        for name in sorted(role_names - protected):
            try:
                connection.execute(
                    sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name))
                )
            except psycopg.Error:
                failed.append(name)
    return failed
