"""Run a baseline and one mutation per clone, and collect the report."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import psycopg

from rlsmatrix.config import MAX_WORKERS, MIN_WORKERS, get_settings
from rlsmatrix.core.equivalence import (
    Fingerprint,
    TableSample,
    describe_difference,
    fingerprint,
    sample_tables,
)
from rlsmatrix.core.probes import run_probes
from rlsmatrix.core.results import (
    BEHAVIOR_DIFFERS,
    LIKELY_EQUIVALENT,
    CampaignReport,
    MutationOutcome,
    ProbeOutcome,
)
from rlsmatrix.db.bootstrap import apply_bootstrap_sql, validate_bootstrap
from rlsmatrix.db.catalog import discover_policies, discover_tables
from rlsmatrix.db.sandbox import (
    Database,
    campaign_lock,
    connect_maintenance,
    create_database,
    drop_database,
    drop_roles,
    list_roles,
)
from rlsmatrix.manifest.models import TestSuite
from rlsmatrix.manifest.validation import validate_suite_probes
from rlsmatrix.mutations import Mutation, generate_mutations, validate_operators
from rlsmatrix.mutations.operators import NO_FORCE_RLS

ProgressCallback = Callable[[str], None]
CountCallback = Callable[[int, int], None]


def _create_template(bootstrap_sql: str) -> Database:
    """Create the database that the baseline and every mutation are cloned from."""
    database = create_database()
    try:
        apply_bootstrap_sql(database.conninfo, bootstrap_sql)
    except BaseException:
        with suppress(Exception):
            drop_database(database.name)
        raise
    return database


def _run_baseline(
    template: Database, suite: TestSuite
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[ProbeOutcome]]:
    database = create_database(template.name)
    try:
        policies = discover_policies(database.conninfo)
        tables = discover_tables(database.conninfo)
        return policies, tables, run_probes(database.conninfo, suite)
    finally:
        drop_database(database.name)


def _classify(probe_outcomes: list[ProbeOutcome]) -> tuple[str, str | None]:
    if any(item.category == "RUNNER_ERROR" for item in probe_outcomes):
        return "ERROR", "One or more probes could not complete reliably."
    if any(not item.passed for item in probe_outcomes):
        return "KILLED", None
    return "SURVIVED", None


class _Reference:
    """Baseline behaviour of the schema, built once and only if it is needed."""

    def __init__(
        self, template: Database, suite: TestSuite, tables: list[dict[str, Any]]
    ) -> None:
        self._template = template
        self._suite = suite
        self._tables = tables
        self._lock = threading.Lock()
        self._value: tuple[list[TableSample], Fingerprint] | None = None

    def get(self) -> tuple[list[TableSample], Fingerprint]:
        with self._lock:
            if self._value is None:
                database = create_database(self._template.name)
                try:
                    samples = sample_tables(database.conninfo, self._tables)
                    reference = fingerprint(database.conninfo, self._suite, samples)
                finally:
                    drop_database(database.name)
                self._value = (samples, reference)
            return self._value


def _assess_survivor(
    outcome: MutationOutcome,
    database: Database,
    suite: TestSuite,
    reference: _Reference,
    connection: psycopg.Connection[Any],
) -> None:
    """Label a survivor as likely equivalent or as a real behaviour change.

    This is advisory: if the analysis fails, the mutation stays unlabelled.
    """
    try:
        samples, expected = reference.get()
        observed = fingerprint(database.conninfo, suite, samples, connection)
    except Exception:
        return
    outcome.difference = describe_difference(expected, observed)
    outcome.equivalence = BEHAVIOR_DIFFERS if outcome.difference else LIKELY_EQUIVALENT
    if (
        outcome.mutation.kind == NO_FORCE_RLS
        and outcome.equivalence == LIKELY_EQUIVALENT
    ):
        # Only the table owner is affected, and the analysis cannot tell whether
        # any declared actor is the owner. "No difference seen" proves nothing.
        outcome.equivalence = None


def _run_mutation(
    template: Database,
    suite: TestSuite,
    mutation: Mutation,
    reference: _Reference,
) -> MutationOutcome:
    started = time.perf_counter()
    admin: psycopg.Connection[Any] | None = None
    database: Database | None = None
    try:
        # One connection creates and drops the clone, and one connection applies
        # the mutation, runs the probes and assesses a survivor.
        admin = connect_maintenance()
        database = create_database(template.name, admin=admin)
        with psycopg.connect(database.conninfo, autocommit=True) as connection:
            connection.execute(mutation.sql, prepare=False)
            probe_outcomes = run_probes(database.conninfo, suite, connection)
            status, error = _classify(probe_outcomes)
            outcome = MutationOutcome(mutation, status, probe_outcomes, error)
            if status == "SURVIVED":
                _assess_survivor(outcome, database, suite, reference, connection)
    except Exception as exc:
        outcome = MutationOutcome(
            mutation, "ERROR", [], error=f"{type(exc).__name__}: {exc}"
        )
    finally:
        if database is not None:
            try:
                drop_database(database.name, admin=admin)
            except Exception as exc:
                message = f"Sandbox teardown failed: {type(exc).__name__}: {exc}"
                outcome.status = "ERROR"
                outcome.error = f"{outcome.error or ''} {message}".strip()
        if admin is not None:
            admin.close()
    outcome.duration_ms = (time.perf_counter() - started) * 1000
    return outcome


def _run_mutations(
    template: Database,
    suite: TestSuite,
    mutations: list[Mutation],
    reference: _Reference,
    workers: int,
    announce: ProgressCallback,
    on_progress: CountCallback | None,
) -> list[MutationOutcome]:
    total = len(mutations)
    if total == 0:
        return []
    results: list[MutationOutcome | None] = [None] * total

    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rlsmatrix")
    try:
        futures = {
            executor.submit(_run_mutation, template, suite, mutation, reference): index
            for index, mutation in enumerate(mutations)
        }
        for done, future in enumerate(as_completed(futures), start=1):
            index = futures[future]
            results[index] = future.result()
            mutation = mutations[index]
            announce(f"Mutation {done}/{total} · {mutation.kind} · {mutation.target}")
            if on_progress is not None:
                on_progress(done, total)
    finally:
        # Drop queued work if the caller is interrupted, for example by a UI rerun.
        executor.shutdown(wait=True, cancel_futures=True)
    return [item for item in results if item is not None]


def run_mutation_campaign(
    bootstrap_sql: str,
    suite: TestSuite,
    progress: ProgressCallback | None = None,
    *,
    workers: int | None = None,
    operators: Collection[str] | None = None,
    on_progress: CountCallback | None = None,
) -> CampaignReport:
    """Run a baseline, then every mutation, each in its own clone of the schema.

    The bootstrap script runs once into a template database. Mutations are
    independent, so they run on a thread pool, and results keep the order in
    which the mutations were generated.
    """
    validate_suite_probes(suite)
    validate_bootstrap(bootstrap_sql)
    selected = validate_operators(operators)
    worker_count = get_settings().workers if workers is None else workers
    if not MIN_WORKERS <= worker_count <= MAX_WORKERS:
        raise ValueError(f"workers must be between {MIN_WORKERS} and {MAX_WORKERS}.")

    started_at = datetime.now(UTC).isoformat()
    clock = time.perf_counter()

    def announce(message: str) -> None:
        if progress is not None:
            progress(message)

    def build_report(
        *,
        baseline_ok: bool,
        policies: list[dict[str, Any]],
        tables: list[dict[str, Any]],
        baseline: list[ProbeOutcome],
        mutations: list[MutationOutcome],
    ) -> CampaignReport:
        return CampaignReport(
            suite_name=suite.name,
            started_at=started_at,
            baseline_ok=baseline_ok,
            policies=policies,
            tables=tables,
            baseline=baseline,
            mutations=mutations,
            duration_seconds=time.perf_counter() - clock,
            workers=worker_count,
            operators=sorted(selected),
        )

    with campaign_lock():
        roles_before = list_roles()
        try:
            announce("Creating disposable baseline database…")
            template = _create_template(bootstrap_sql)
            try:
                policies, tables, baseline = _run_baseline(template, suite)
                if not all(result.passed for result in baseline):
                    announce(
                        "Baseline failed. Mutations skipped until assertions pass."
                    )
                    return build_report(
                        baseline_ok=False,
                        policies=policies,
                        tables=tables,
                        baseline=baseline,
                        mutations=[],
                    )

                mutations = generate_mutations(policies, tables, selected)
                settings = get_settings()
                if len(mutations) > settings.max_mutations:
                    raise ValueError(
                        f"The campaign generated {len(mutations)} mutations, "
                        f"exceeding the configured limit of {settings.max_mutations}. "
                        "Narrow the schema, select fewer operators, or increase "
                        "RLSMATRIX_MAX_MUTATIONS."
                    )
                if not mutations:
                    announce("No applicable RLS mutations were discovered.")

                reference = _Reference(
                    template, suite, [t for t in tables if t["rowsecurity"]]
                )
                outcomes = _run_mutations(
                    template,
                    suite,
                    mutations,
                    reference,
                    worker_count,
                    announce,
                    on_progress,
                )
                announce("Mutation campaign complete.")
                return build_report(
                    baseline_ok=True,
                    policies=policies,
                    tables=tables,
                    baseline=baseline,
                    mutations=outcomes,
                )
            finally:
                drop_database(template.name)
        finally:
            leftover = drop_roles(list_roles() - roles_before)
            if leftover:
                announce(f"Could not remove sandbox role(s): {', '.join(leftover)}")
