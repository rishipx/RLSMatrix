from rlsmatrix.core.results import CampaignReport, MutationOutcome
from rlsmatrix.mutations import Mutation


def _mutation_outcome(status: str) -> MutationOutcome:
    return MutationOutcome(
        mutation=Mutation(
            id="mutation_1",
            kind="OPEN_USING",
            target="public.docs.policy",
            description="Open policy predicate",
            sql="ALTER POLICY policy ON public.docs USING (true)",
        ),
        status=status,
        probe_outcomes=[],
    )


def test_mutation_score_excludes_errors() -> None:
    report = CampaignReport(
        suite_name="Test",
        started_at="2026-01-01T00:00:00+00:00",
        baseline_ok=True,
        policies=[],
        tables=[],
        baseline=[],
        mutations=[
            _mutation_outcome("KILLED"),
            _mutation_outcome("SURVIVED"),
            _mutation_outcome("ERROR"),
        ],
    )
    assert report.killed == 1
    assert report.survived == 1
    assert report.errors == 1
    assert report.mutation_score == 50.0


def test_empty_mutation_score_is_none() -> None:
    report = CampaignReport(
        suite_name="Test",
        started_at="2026-01-01T00:00:00+00:00",
        baseline_ok=True,
        policies=[],
        tables=[],
        baseline=[],
        mutations=[],
    )
    assert report.mutation_score is None


def _survivor(equivalence: str | None) -> MutationOutcome:
    outcome = MutationOutcome(
        mutation=Mutation("id", "WIDEN_TO_PUBLIC", "public.t.p", "d", "SELECT 1"),
        status="SURVIVED",
        probe_outcomes=[],
    )
    outcome.equivalence = equivalence
    return outcome


def _killed() -> MutationOutcome:
    return MutationOutcome(
        mutation=Mutation("k", "OPEN_USING", "public.t.p", "d", "SELECT 1"),
        status="KILLED",
        probe_outcomes=[],
    )


def _report(mutations: list[MutationOutcome]) -> CampaignReport:
    return CampaignReport("s", "t", True, [], [], [], mutations)


def test_adjusted_score_leaves_out_likely_equivalent_survivors() -> None:
    report = _report(
        [
            _killed(),
            _survivor("likely_equivalent"),
            _survivor("likely_equivalent"),
            _survivor("behavior_differs"),
        ]
    )
    assert report.mutation_score == 25.0
    assert report.likely_equivalent == 2
    assert report.adjusted_score == 50.0


def test_adjusted_score_equals_the_score_when_nothing_is_equivalent() -> None:
    report = _report([_killed(), _survivor("behavior_differs"), _survivor(None)])
    assert report.adjusted_score == report.mutation_score


def test_adjusted_score_is_undefined_when_every_mutation_is_equivalent() -> None:
    report = _report([_survivor("likely_equivalent")])
    assert report.adjusted_score is None


def test_equivalence_fields_are_in_the_json_report() -> None:
    survivor = _survivor("behavior_differs")
    survivor.difference = "As alice, ..."
    data = _report([_killed(), survivor]).to_dict()
    assert data["likely_equivalent"] == 0
    assert data["mutations"][1]["equivalence"] == "behavior_differs"
    assert data["mutations"][1]["difference"] == "As alice, ..."
    assert data["mutations"][0]["equivalence"] is None
