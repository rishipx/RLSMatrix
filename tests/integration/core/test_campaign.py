import subprocess
import sys

import psycopg
import pytest

from rlsmatrix.core.campaign import run_mutation_campaign
from rlsmatrix.db.connection import connection_info
from rlsmatrix.db.sandbox import (
    CampaignBusyError,
    campaign_lock,
    drop_roles,
    list_roles,
)
from rlsmatrix.examples import DIRECTORY as EXAMPLES
from rlsmatrix.manifest import load_test_suite

pytestmark = pytest.mark.integration


def _run(example: str, suite: str = "suite.yaml", **kwargs):
    bootstrap = (EXAMPLES / example / "schema.sql").read_text(encoding="utf-8")
    manifest = (EXAMPLES / example / suite).read_text(encoding="utf-8")
    return run_mutation_campaign(bootstrap, load_test_suite(manifest), **kwargs)


@pytest.mark.parametrize(
    ("example", "suite", "score"),
    [
        ("tenant_isolation", "suite_first_draft.yaml", 28.6),
        ("tenant_isolation", "suite.yaml", 71.4),
        ("org_projects", "suite.yaml", 100.0),
        ("support_tickets", "suite.yaml", 64.3),
        ("shared_notes", "suite_first_draft.yaml", 100.0),
        ("shared_notes", "suite.yaml", 100.0),
    ],
)
def test_bundled_examples_have_stable_scores(
    example: str, suite: str, score: float
) -> None:
    report = _run(example, suite)
    assert report.baseline_ok
    assert report.errors == 0, [m.error for m in report.mutations]
    assert report.mutation_score == score


def _labels(report) -> list[str | None]:
    return [m.equivalence for m in report.mutations if m.status == "SURVIVED"]


def test_harmless_survivors_are_labelled_likely_equivalent() -> None:
    report = _run("support_tickets")
    assert report.survived == 5
    assert set(_labels(report)) == {"likely_equivalent"}
    assert report.adjusted_score == 100.0


def test_real_gaps_are_explained_and_harmless_survivors_are_not() -> None:
    report = _run("tenant_isolation", "suite_first_draft.yaml")
    by_kind = {(m.mutation.kind, m.mutation.target): m for m in report.mutations}
    select_gap = by_kind[("OPEN_USING", "public.documents.documents_select_own")]
    assert select_gap.equivalence == "behavior_differs"
    assert select_gap.difference is not None
    assert "SELECT all rows" in select_gap.difference
    harmless = by_kind[("WIDEN_TO_PUBLIC", "public.documents.documents_select_own")]
    assert harmless.equivalence == "likely_equivalent"
    assert harmless.difference is None


def test_only_survivors_are_assessed() -> None:
    report = _run("tenant_isolation")
    assert all(m.equivalence is None for m in report.mutations if m.status == "KILLED")


def test_the_analysis_never_calls_a_detected_mutation_equivalent() -> None:
    """Every mutation the probes killed must also change observable behaviour."""
    from rlsmatrix.core import campaign
    from rlsmatrix.core.equivalence import (
        describe_difference,
        fingerprint,
        sample_tables,
    )
    from rlsmatrix.db.sandbox import create_database, drop_database
    from rlsmatrix.mutations import generate_mutations

    folder = EXAMPLES / "org_projects"
    suite = load_test_suite((folder / "suite.yaml").read_text("utf-8"))
    before = list_roles()
    template = campaign._create_template((folder / "schema.sql").read_text("utf-8"))
    try:
        policies, tables, _ = campaign._run_baseline(template, suite)
        clone = create_database(template.name)
        try:
            samples = sample_tables(
                clone.conninfo, [t for t in tables if t["rowsecurity"]]
            )
            reference = fingerprint(clone.conninfo, suite, samples)
        finally:
            drop_database(clone.name)
        for mutation in generate_mutations(policies, tables):
            clone = create_database(template.name)
            try:
                with psycopg.connect(clone.conninfo, autocommit=True) as connection:
                    connection.execute(mutation.sql, prepare=False)
                observed = fingerprint(clone.conninfo, suite, samples)
            finally:
                drop_database(clone.name)
            assert describe_difference(reference, observed), mutation.id
    finally:
        drop_database(template.name)
        drop_roles(list_roles() - before)


def test_campaign_leaves_no_roles_behind() -> None:
    before = list_roles()
    _run("tenant_isolation")
    assert list_roles() == before


def test_campaigns_can_run_back_to_back() -> None:
    """Roles are cluster-wide; a second campaign must not collide with the first."""
    assert _run("tenant_isolation").errors == 0
    assert _run("tenant_isolation").errors == 0


def test_existing_roles_are_reused_by_the_bootstrap() -> None:
    with psycopg.connect(connection_info(), autocommit=True) as connection:
        connection.execute("DROP ROLE IF EXISTS anon")
        connection.execute("CREATE ROLE anon NOLOGIN")
    try:
        assert _run("tenant_isolation").errors == 0
    finally:
        with psycopg.connect(connection_info(), autocommit=True) as connection:
            connection.execute("DROP ROLE IF EXISTS anon")


def test_parallel_and_serial_runs_agree_in_the_same_order() -> None:
    serial = _run("org_projects", workers=1)
    parallel = _run("org_projects", workers=8)
    assert [(m.mutation.id, m.status) for m in serial.mutations] == [
        (m.mutation.id, m.status) for m in parallel.mutations
    ]


def test_operator_selection_limits_the_campaign() -> None:
    report = _run("tenant_isolation", operators=["DROP_POLICY"])
    assert {m.mutation.kind for m in report.mutations} == {"DROP_POLICY"}


def test_a_second_campaign_is_refused_while_one_is_running() -> None:
    with campaign_lock(), pytest.raises(CampaignBusyError):
        _run("tenant_isolation")


def test_failed_baseline_skips_mutations_and_cleans_up() -> None:
    before = list_roles()
    bootstrap = (EXAMPLES / "tenant_isolation" / "schema.sql").read_text("utf-8")
    manifest = (EXAMPLES / "tenant_isolation" / "suite.yaml").read_text("utf-8")
    broken = manifest.replace("      - [1]\n      - [2]", "      - [99]")
    assert broken != manifest
    report = run_mutation_campaign(bootstrap, load_test_suite(broken))
    assert not report.baseline_ok
    assert report.mutations == []
    assert list_roles() == before


def test_bootstrap_failure_cleans_up_databases_and_roles() -> None:
    before = list_roles()
    suite = load_test_suite((EXAMPLES / "tenant_isolation" / "suite.yaml").read_text())
    script = "CREATE ROLE rlsmatrix_scratch NOLOGIN; SELECT * FROM missing_table;"
    with pytest.raises(psycopg.Error):
        run_mutation_campaign(script, suite)
    assert list_roles() == before
    with psycopg.connect(connection_info(), autocommit=True) as connection:
        row = connection.execute(
            "SELECT count(*) FROM pg_database WHERE datname LIKE 'rlsmatrix\\_%'"
        ).fetchone()
    assert row is not None and row[0] == 0


@pytest.mark.parametrize(
    ("example", "suite"),
    [
        ("tenant_isolation", "suite.yaml"),
        ("org_projects", "suite.yaml"),
        ("support_tickets", "suite.yaml"),
        ("shared_notes", "suite.yaml"),
        ("owner_force_rls", "suite.yaml"),
    ],
)
def test_every_operator_produces_valid_sql_on_every_example(
    example: str, suite: str
) -> None:
    report = _run(example, suite, operators=["all"])
    assert report.baseline_ok
    assert report.errors == 0, [m.error for m in report.mutations]


def test_predicate_operators_expose_gaps_that_core_operators_miss() -> None:
    core = _run("shared_notes", "suite_first_draft.yaml")
    assert core.mutation_score == 100.0

    fine = _run(
        "shared_notes", "suite_first_draft.yaml", operators=["core", "predicate"]
    )
    survivors = [m for m in fine.mutations if m.status == "SURVIVED"]
    assert {m.mutation.kind for m in survivors} == {"DROP_CLAUSE"}
    assert len(survivors) == 2
    assert {m.equivalence for m in survivors} == {"behavior_differs"}

    improved = _run("shared_notes", "suite.yaml", operators=["core", "predicate"])
    assert improved.mutation_score == 100.0


def test_the_lock_is_released_when_a_campaign_ends() -> None:
    with campaign_lock():
        pass
    with campaign_lock():
        pass


def test_a_separate_process_is_refused_while_a_campaign_is_running() -> None:
    probe = (
        "import sys\n"
        "from rlsmatrix.db.sandbox import CampaignBusyError, campaign_lock\n"
        "try:\n"
        "    with campaign_lock():\n"
        "        sys.exit(0)\n"
        "except CampaignBusyError:\n"
        "    sys.exit(7)\n"
    )

    def attempt() -> int:
        return subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, timeout=60
        ).returncode

    with campaign_lock():
        assert attempt() == 7
    assert attempt() == 0


def test_removing_force_rls_is_caught_only_when_an_actor_owns_the_table() -> None:
    with_owner = _run("owner_force_rls", "suite.yaml", operators=["NO_FORCE_RLS"])
    assert [m.status for m in with_owner.mutations] == ["KILLED"]

    without = _run("owner_force_rls", "suite_no_owner.yaml", operators=["NO_FORCE_RLS"])
    (survivor,) = without.mutations
    assert survivor.status == "SURVIVED"
    # The analysis cannot see the owner, so it must not call this harmless.
    assert survivor.equivalence is None
    assert without.adjusted_score == without.mutation_score


def test_org_projects_hides_a_command_widening_gap_from_the_core_operators() -> None:
    assert _run("org_projects").mutation_score == 100.0
    wide = _run("org_projects", operators=["WIDEN_COMMAND"])
    gaps = [m for m in wide.mutations if m.equivalence == "behavior_differs"]
    assert [m.mutation.target for m in gaps] == [
        "public.projects.projects_hide_archived"
    ]
