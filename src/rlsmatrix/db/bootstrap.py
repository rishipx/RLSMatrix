"""Validate and run the schema script in a template database."""

from __future__ import annotations

import psycopg
import sqlparse
from pglast import ast, parse_sql
from psycopg import sql

from rlsmatrix.config import get_settings


def validate_bootstrap(bootstrap_sql: str) -> None:
    if not bootstrap_sql.strip():
        raise ValueError("Bootstrap SQL cannot be empty.")
    if len(bootstrap_sql.encode("utf-8")) > get_settings().max_bootstrap_bytes:
        raise ValueError("Bootstrap SQL exceeds the configured size limit")


def _created_role_name(statement: str) -> str | None:
    lowered = statement.lower()
    if not any(word in lowered for word in ("role", "user", "group")):
        return None
    try:
        parsed = parse_sql(statement)
    except Exception:
        return None  # Not parseable here; let PostgreSQL report the real error.
    if len(parsed) != 1:
        return None
    node = parsed[0].stmt
    return str(node.role) if isinstance(node, ast.CreateRoleStmt) else None


def apply_bootstrap_sql(conninfo: str, bootstrap_sql: str) -> None:
    """Run the bootstrap script in one transaction.

    Roles are cluster-wide, so ``CREATE ROLE`` is skipped for roles that
    already exist instead of failing with ``DuplicateObject``.
    """
    validate_bootstrap(bootstrap_sql)
    statements = [
        statement.strip()
        for statement in sqlparse.split(bootstrap_sql)
        if statement.strip()
    ]

    timeout_ms = get_settings().statement_timeout_ms * 2
    with psycopg.connect(conninfo) as connection:
        connection.execute(
            sql.SQL("SET LOCAL statement_timeout = {}").format(
                sql.Literal(f"{timeout_ms}ms")
            )
        )
        existing_roles = {
            row[0] for row in connection.execute("SELECT rolname FROM pg_roles")
        }
        for statement in statements:
            role = _created_role_name(statement)
            if role is not None and role in existing_roles:
                continue
            connection.execute(statement, prepare=False)
            if role is not None:
                existing_roles.add(role)
