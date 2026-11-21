"""Allow only a single data-manipulation statement per probe."""

from __future__ import annotations

from pglast import parse_sql

from rlsmatrix.config import get_settings
from rlsmatrix.manifest.models import TestSuite

ALLOWED_STATEMENTS = frozenset({"SelectStmt", "InsertStmt", "UpdateStmt", "DeleteStmt"})


def validate_probe_sql(statement: str) -> str:
    """Allow exactly one SELECT, INSERT, UPDATE or DELETE statement."""
    if not statement or not statement.strip():
        raise ValueError("Probe SQL cannot be empty")

    if len(statement.encode("utf-8")) > get_settings().max_probe_sql_bytes:
        raise ValueError("Probe SQL exceeds the configured size limit")

    try:
        parsed = parse_sql(statement)
    except Exception as exc:
        raise ValueError(f"Could not parse probe SQL: {exc}") from exc

    if len(parsed) != 1:
        raise ValueError("Each probe must contain exactly one SQL statement")

    statement_type = type(parsed[0].stmt).__name__
    if statement_type not in ALLOWED_STATEMENTS:
        allowed = ", ".join(sorted(ALLOWED_STATEMENTS))
        raise ValueError(
            f"{statement_type} is not allowed in a probe. Allowed: {allowed}"
        )
    return statement_type


def validate_suite_probes(suite: TestSuite) -> None:
    for probe in suite.probes:
        try:
            validate_probe_sql(probe.sql)
        except ValueError as exc:
            raise ValueError(f"Probe '{probe.id}': {exc}") from exc
