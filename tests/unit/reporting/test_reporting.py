from rlsmatrix.core.results import CampaignReport, MutationOutcome, ProbeOutcome
from rlsmatrix.mutations import Mutation
from rlsmatrix.reporting import render_markdown, render_text


def _probe(probe_id: str, passed: bool, category: str = "ASSERTION") -> ProbeOutcome:
    return ProbeOutcome(
        id=probe_id,
        actor="alice",
        passed=passed,
        expected_rows=[],
        actual_rows=[],
        category=category,
        message="m",
    )


def _outcome(kind: str, status: str, probes: list[ProbeOutcome]) -> MutationOutcome:
    return MutationOutcome(
        mutation=Mutation("id_" + kind, kind, "public.t.p", "d", "SELECT 1"),
        status=status,
        probe_outcomes=probes,
    )


def _report() -> CampaignReport:
    return CampaignReport(
        suite_name="Suite",
        started_at="2026-01-01T00:00:00+00:00",
        baseline_ok=True,
        policies=[],
        tables=[],
        baseline=[_probe("p1", True), _probe("p2", True), _probe("unused", True)],
        mutations=[
            _outcome("OPEN_USING", "KILLED", [_probe("p1", False), _probe("p2", True)]),
            _outcome(
                "OPEN_WITH_CHECK", "KILLED", [_probe("p1", False), _probe("p2", False)]
            ),
            _outcome("DISABLE_RLS", "SURVIVED", [_probe("p1", True)]),
        ],
        duration_seconds=1.5,
        workers=2,
    )


def test_killed_by_lists_failed_probes_only() -> None:
    assert _report().mutations[1].killed_by == ["p1", "p2"]


def test_runner_errors_do_not_count_as_kills() -> None:
    outcome = _outcome("X", "ERROR", [_probe("p1", False, "RUNNER_ERROR")])
    assert outcome.killed_by == []


def test_by_operator_groups_statuses() -> None:
    grouped = _report().by_operator()
    assert grouped["DISABLE_RLS"] == {"KILLED": 0, "SURVIVED": 1, "ERROR": 0}
    assert grouped["OPEN_USING"]["KILLED"] == 1


def test_to_dict_is_json_serialisable_and_has_new_fields() -> None:
    import json

    data = _report().to_dict()
    json.dumps(data)
    assert data["workers"] == 2
    assert data["mutations"][2]["hint"]  # survivors carry a hint
    assert data["mutations"][0]["hint"] is None


def test_markdown_lists_survivors_with_hint() -> None:
    text = render_markdown(_report())
    assert "**Mutation score: 66.7%**" in text
    assert "### `DISABLE_RLS` on `public.t.p`" in text
    assert "> No probe depends on RLS" in text


def test_markdown_for_failed_baseline_is_a_short_failure_table() -> None:
    report = _report()
    report.baseline_ok = False
    report.baseline = [_probe("p1", False)]
    text = render_markdown(report)
    assert "baseline failed" in text.lower() and "| `p1` |" in text
    assert "Mutation score" not in text


def test_text_report_shows_killers() -> None:
    assert "<- p1, p2" in render_text(_report())


def _with_assessments() -> CampaignReport:
    report = _report()
    equivalent = _outcome("WIDEN_TO_PUBLIC", "SURVIVED", [_probe("p1", True)])
    equivalent.equivalence = "likely_equivalent"
    differs = _outcome("OPEN_USING", "SURVIVED", [_probe("p1", True)])
    differs.equivalence = "behavior_differs"
    differs.difference = "As bob, SELECT all rows on public.t: 1 before, 2 after."
    report.mutations = [report.mutations[0], equivalent, differs]
    return report


def test_text_report_tags_survivors_and_shows_the_adjusted_score() -> None:
    text = render_text(_with_assessments())
    assert "adjusted score: 50.0%  (likely-equivalent survivors left out: 1)" in text
    assert "[likely equivalent]" in text
    assert "[changes behavior]" in text


def test_text_report_omits_the_adjusted_line_without_equivalent_survivors() -> None:
    assert "adjusted score" not in render_text(_report())


def test_markdown_explains_each_kind_of_survivor() -> None:
    text = render_markdown(_with_assessments())
    assert (
        "With likely-equivalent survivors left out (1), the score is **50.0%**" in text
    )
    assert "**Likely equivalent.**" in text
    assert "**Changes behavior.** As bob, SELECT all rows on public.t" in text
    # A harmless survivor needs no advice; a real gap still gets its hint.
    assert text.count("> No probe") == 1


def test_text_report_aligns_targets_for_long_operator_names() -> None:
    report = _report()
    report.mutations.append(_outcome("RESTRICTIVE_TO_PERMISSIVE", "SURVIVED", []))
    rows = [
        line
        for line in render_text(report).splitlines()
        if line.startswith(("  KILLED", "  SURVIVED"))
    ]
    assert len({row.index("public.t.p") for row in rows}) == 1


def test_text_report_keeps_the_compact_layout_for_short_operator_names() -> None:
    rows = [
        line
        for line in render_text(_report()).splitlines()
        if line.startswith(("  KILLED", "  SURVIVED"))
    ]
    assert all(row.index("public.t.p") == len("  SURVIVED ") + 16 + 1 for row in rows)
