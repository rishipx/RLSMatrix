"""Read policies and tables from the PostgreSQL catalogs."""

from __future__ import annotations

import psycopg

_SYSTEM_SCHEMAS = "('pg_catalog', 'information_schema', 'pg_toast')"

_POLICIES_QUERY = f"""
    SELECT schemaname, tablename, policyname, permissive, roles, cmd,
           qual, with_check
    FROM pg_policies
    WHERE schemaname NOT IN {_SYSTEM_SCHEMAS}
    ORDER BY schemaname, tablename, policyname
"""

_TABLES_QUERY = f"""
    SELECT n.nspname AS schemaname,
           c.relname AS tablename,
           c.relrowsecurity AS rowsecurity,
           c.relforcerowsecurity AS forcerowsecurity
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p')
      AND n.nspname NOT IN {_SYSTEM_SCHEMAS}
    ORDER BY n.nspname, c.relname
"""


def _fetch_dicts(conninfo: str, query: str) -> list[dict[str, object]]:
    with psycopg.connect(conninfo) as connection:
        cursor = connection.execute(query)
        rows = cursor.fetchall()
        columns = [column.name for column in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def discover_policies(conninfo: str) -> list[dict[str, object]]:
    return _fetch_dicts(conninfo, _POLICIES_QUERY)


def discover_tables(conninfo: str) -> list[dict[str, object]]:
    return _fetch_dicts(conninfo, _TABLES_QUERY)
