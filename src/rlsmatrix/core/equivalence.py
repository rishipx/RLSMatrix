"""Tell apart surviving mutations that changed nothing from real test gaps.

A mutation that no probe detects is either harmless in this schema (an
"equivalent" mutation) or a behaviour change the suite missed. To decide, the
same battery of statements is run as every actor on the baseline and on the
mutated schema: read each table, delete from it, update it (also changing
single columns), and insert copies of its existing rows. If every outcome is
identical, the mutation is *likely* equivalent. If any differs, it is a real
change, and the first difference says which probe to write.

The result depends on the actors and fixture rows in the suite, which is why
it is only ever reported as "likely".
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql

from rlsmatrix.core.probes import begin_as_actor, normalize
from rlsmatrix.db.connection import Session
from rlsmatrix.manifest.models import Actor, TestSuite

MAX_SAMPLE_ROWS = 8
MAX_VALUES_PER_COLUMN = 3
MAX_ROWS_READ = 1_000


@dataclass(frozen=True, slots=True)
class TableSample:
    """Rows read from a table as the sandbox administrator."""

    schema: str
    table: str
    columns: list[str]
    rows: list[dict[str, Any]]

    @property
    def name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def ref(self) -> sql.Composed:
        return sql.SQL("{}.{}").format(
            sql.Identifier(self.schema), sql.Identifier(self.table)
        )

    def distinct_values(self, column: str) -> list[Any]:
        seen: dict[str, Any] = {}
        for row in self.rows:
            value = row.get(column)
            if value is not None:
                seen.setdefault(json.dumps(value, sort_keys=True), value)
        return list(seen.values())[:MAX_VALUES_PER_COLUMN]


@dataclass(frozen=True, slots=True)
class Observation:
    actor: str
    table: str
    label: str
    signature: str  # compared between baseline and mutated schema
    summary: str  # shown to people


Fingerprint = dict[str, Observation]


def sample_tables(conninfo: str, tables: list[dict[str, Any]]) -> list[TableSample]:
    """Read a few rows from every RLS-protected table, bypassing RLS."""
    samples: list[TableSample] = []
    with psycopg.connect(conninfo) as connection:
        for table in tables:
            if not table.get("rowsecurity"):
                continue
            schema, name = str(table["schemaname"]), str(table["tablename"])
            ref = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))
            cursor = connection.execute(sql.SQL("SELECT * FROM {} LIMIT 0").format(ref))
            columns = [column.name for column in cursor.description or []]
            rows = connection.execute(
                sql.SQL(
                    "SELECT to_jsonb(t) FROM {} AS t "
                    "ORDER BY to_jsonb(t)::text LIMIT {}"
                ).format(ref, sql.Literal(MAX_SAMPLE_ROWS))
            ).fetchall()
            samples.append(TableSample(schema, name, columns, [row[0] for row in rows]))
    return samples


def _classify_error(exc: psycopg.Error) -> tuple[str, str]:
    state = exc.sqlstate or "unknown"
    if "row-level security" in str(exc).lower():
        return "rls", "rejected by row-level security"
    if state == "42501":
        return "denied", "rejected: permission denied"
    if state.startswith("23"):
        # Integrity errors are raised after the RLS checks have passed.
        return "allowed", "allowed (then failed a constraint)"
    return f"error:{state}", f"failed with SQLSTATE {state}"


def _battery(
    sample: TableSample,
) -> Iterator[tuple[str, str, sql.SQL | sql.Composed, tuple[str, ...], str]]:
    """Yield ``(key, label, statement, params, mode)`` for one table."""
    ref = sample.ref
    yield (
        "select",
        "SELECT all rows",
        sql.SQL("SELECT to_jsonb(t) FROM {} AS t").format(ref),
        (),
        "rows",
    )
    yield (
        "delete",
        "DELETE all rows",
        sql.SQL("DELETE FROM {}").format(ref),
        (),
        "count",
    )

    if sample.columns:
        assignments = sql.SQL(", ").join(
            sql.SQL("{0} = {0}").format(sql.Identifier(column))
            for column in sample.columns
        )
        yield (
            "update-all",
            "UPDATE all rows without changing them",
            sql.SQL("UPDATE {} SET {}").format(ref, assignments),
            (),
            "count",
        )

    for column in sample.columns:
        for value in sample.distinct_values(column):
            shown = json.dumps(value)
            yield (
                f"update {column}={shown}",
                f"UPDATE setting {column} to {shown}",
                sql.SQL(
                    "UPDATE {} SET {} = (jsonb_populate_record(NULL::{}, %s::jsonb)).{}"
                ).format(ref, sql.Identifier(column), ref, sql.Identifier(column)),
                (json.dumps({column: value}),),
                "count",
            )

    first = sample.columns[0] if sample.columns else None
    for index, row in enumerate(sample.rows):
        who = f"row with {first}={json.dumps(row.get(first))}" if first else "a row"
        yield (
            f"insert row {index}",
            f"INSERT a copy of the {who}",
            sql.SQL(
                "INSERT INTO {} SELECT * FROM jsonb_populate_record(NULL::{}, %s::jsonb)"
            ).format(ref, ref),
            (json.dumps(row),),
            "insert",
        )


def _observe(
    connection: psycopg.Connection[Any],
    actor: Actor,
    sample: TableSample,
    label: str,
    statement: sql.SQL | sql.Composed,
    params: tuple[str, ...],
    mode: str,
) -> Observation:
    try:
        begin_as_actor(connection, actor)
        cursor = connection.execute(statement, params, prepare=False)
        if mode == "rows":
            fetched = cursor.fetchmany(MAX_ROWS_READ)
            rows = sorted(
                json.dumps(normalize(row[0]), sort_keys=True) for row in fetched
            )
            signature, summary = "\n".join(rows), f"{len(rows)} row(s) visible"
        elif mode == "count":
            signature = str(cursor.rowcount)
            summary = f"{cursor.rowcount} row(s) affected"
        else:
            signature, summary = "allowed", "allowed"
    except psycopg.Error as exc:
        signature, summary = _classify_error(exc)
    finally:
        try:
            if not connection.closed:
                connection.execute("ROLLBACK")
        except psycopg.Error:
            pass
    return Observation(actor.id, sample.name, label, signature, summary)


def fingerprint(
    conninfo: str,
    suite: TestSuite,
    samples: list[TableSample],
    connection: psycopg.Connection[Any] | None = None,
) -> Fingerprint:
    """Record what every actor can do to every sampled table."""
    # The statements depend only on the table, so build them once for all actors.
    batteries = [(sample, list(_battery(sample))) for sample in samples]
    observed: Fingerprint = {}
    with Session(conninfo, connection) as session:
        for actor in suite.actors:
            for sample, battery in batteries:
                for key, label, statement, params, mode in battery:
                    observed[f"{actor.id}|{sample.name}|{key}"] = _observe(
                        session.connection,
                        actor,
                        sample,
                        label,
                        statement,
                        params,
                        mode,
                    )
    return observed


def describe_difference(expected: Fingerprint, observed: Fingerprint) -> str | None:
    """Describe how ``observed`` differs from ``expected``, or return ``None``."""
    differences = [
        (before, observed[key])
        for key, before in expected.items()
        if key in observed and observed[key].signature != before.signature
    ]
    if not differences:
        return None
    before, after = differences[0]
    text = (
        f"As {before.actor}, {before.label} on {before.table}: "
        f"{before.summary} before the change, {after.summary} after it."
    )
    if len(differences) > 1:
        text += f" {len(differences) - 1} more behaviour change(s) were found."
    return text
