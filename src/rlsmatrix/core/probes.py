"""Run probes as an actor inside a rolled-back transaction."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql

from rlsmatrix.config import get_settings
from rlsmatrix.core.results import ProbeOutcome
from rlsmatrix.db.connection import Session
from rlsmatrix.manifest.models import Actor, Probe, TestSuite

_CONNECTION_ERRORS = (psycopg.OperationalError, psycopg.InterfaceError)


class ProbeLimitError(RuntimeError):
    """A probe returned more rows than the configured limit."""


def normalize(value: Any) -> Any:
    """Convert database values to JSON-friendly, comparable Python values."""
    if isinstance(value, datetime | date | dt_time):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, bytes | bytearray):
        return bytes(value).hex()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, memoryview):
        return value.tobytes().hex()
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [normalize(item) for item in value]
    return value


def _claims(actor: Actor) -> dict[str, Any]:
    claims = dict(actor.claims)
    if actor.sub is not None:
        claims.setdefault("sub", actor.sub)
    claims.setdefault("role", actor.role)
    return claims


def begin_as_actor(connection: psycopg.Connection[Any], actor: Actor) -> None:
    """Open a transaction in which statements run as ``actor``.

    The caller must end it with ROLLBACK.
    """
    settings = get_settings()
    claims = _claims(actor)
    connection.execute("BEGIN")
    connection.execute(
        "SELECT set_config('statement_timeout', %s, true), "
        "set_config('lock_timeout', %s, true), "
        "set_config('request.jwt.claim.sub', %s, true), "
        "set_config('request.jwt.claims', %s, true)",
        (
            f"{settings.statement_timeout_ms}ms",
            f"{settings.lock_timeout_ms}ms",
            str(claims.get("sub") or ""),
            json.dumps(claims),
        ),
    )
    connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(actor.role)))


def _execute_probe(
    connection: psycopg.Connection[Any], probe: Probe, actor: Actor
) -> list[list[Any]]:
    settings = get_settings()
    begin_as_actor(connection, actor)
    cursor = connection.execute(probe.sql, prepare=False)
    if cursor.description is None:
        return []
    rows = cursor.fetchmany(settings.max_result_rows + 1)
    if len(rows) > settings.max_result_rows:
        raise ProbeLimitError(
            "Probe result exceeds the configured row limit "
            f"({settings.max_result_rows}). Add a selective predicate."
        )
    return [normalize(list(row)) for row in rows]


def run_probe(
    connection: psycopg.Connection[Any], probe: Probe, actor: Actor
) -> ProbeOutcome:
    actual_rows: list[list[Any]] = []
    query_error: psycopg.Error | None = None
    runner_error: Exception | None = None

    try:
        actual_rows = _execute_probe(connection, probe, actor)
    except psycopg.Error as exc:
        query_error = exc
    except Exception as exc:
        runner_error = exc
    finally:
        try:
            if not connection.closed:
                connection.execute("ROLLBACK")
        except Exception as exc:
            runner_error = runner_error or exc

    expected_rows = normalize(probe.expected_rows)

    def outcome(
        *, passed: bool, message: str, category: str, error: str | None = None
    ) -> ProbeOutcome:
        return ProbeOutcome(
            id=probe.id,
            actor=probe.actor,
            passed=passed,
            expected_rows=expected_rows,
            actual_rows=actual_rows,
            expected_error=probe.expect_error,
            error=error,
            message=message,
            category=category,
        )

    if runner_error is not None:
        return outcome(
            passed=False,
            message=(
                "Probe runner failed; this result cannot be counted as a mutation kill."
            ),
            category="RUNNER_ERROR",
            error=f"{type(runner_error).__name__}: {runner_error}",
        )

    if query_error is not None:
        error_text = str(query_error).strip()
        is_connection_error = isinstance(query_error, _CONNECTION_ERRORS)
        expected_error = probe.expect_error
        passed = (
            not is_connection_error
            and expected_error is not None
            and expected_error.casefold() in error_text.casefold()
        )
        return outcome(
            passed=passed,
            message=(
                f"Matched expected database error: {expected_error}"
                if passed
                else "Unexpected database error."
            ),
            category="RUNNER_ERROR" if is_connection_error else "DATABASE_ERROR",
            error=error_text,
        )

    if probe.expect_error is not None:
        return outcome(
            passed=False,
            message=(
                f"Expected an error containing '{probe.expect_error}', "
                "but the query succeeded."
            ),
            category="ASSERTION",
        )

    passed = actual_rows == expected_rows
    return outcome(
        passed=passed,
        message=(
            "Rows matched the assertion."
            if passed
            else "Returned rows did not match the assertion."
        ),
        category="ASSERTION",
    )


def run_probes(
    conninfo: str,
    suite: TestSuite,
    connection: psycopg.Connection[Any] | None = None,
) -> list[ProbeOutcome]:
    """Run every probe of ``suite``, on ``connection`` when one is given."""
    actors = {actor.id: actor for actor in suite.actors}
    with Session(conninfo, connection) as session:
        return [
            run_probe(session.connection, probe, actors[probe.actor])
            for probe in suite.probes
        ]
