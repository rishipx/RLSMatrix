from rlsmatrix.ui import tables

REPORT = {
    "baseline": [{"id": "p1"}, {"id": "p2"}],
    "mutations": [
        {
            "mutation": {"kind": "OPEN_USING", "target": "public.t.pol"},
            "status": "KILLED",
            "killed_by": ["p1"],
            "duration_ms": 12.4,
            "equivalence": None,
        },
        {
            "mutation": {"kind": "DISABLE_RLS", "target": "public.t"},
            "status": "SURVIVED",
            "killed_by": [],
            "duration_ms": 8.0,
            "equivalence": "likely_equivalent",
        },
    ],
    "by_operator": {
        "DISABLE_RLS": {"KILLED": 0, "SURVIVED": 1, "ERROR": 0},
        "OPEN_USING": {"KILLED": 1, "SURVIVED": 0, "ERROR": 0},
    },
}


def test_coverage_matrix_marks_only_the_probes_that_detected_a_mutation() -> None:
    frame = tables.coverage_matrix(REPORT).data
    assert list(frame.columns) == ["Operator", "Target", "Result", "p1", "p2"]
    assert frame.loc[0, "p1"] == tables.DETECTED
    assert frame.loc[0, "p2"] == ""
    assert (frame.loc[1, ["p1", "p2"]] == "").all()
    assert list(frame["Result"]) == ["Killed", "Survived"]


def test_coverage_matrix_renders_without_error() -> None:
    assert "background-color" in tables.coverage_matrix(REPORT).to_html()


def test_mutations_table_lists_detecting_probes() -> None:
    frame = tables.mutations_table(REPORT)
    assert list(frame["Detected by"]) == ["p1", ""]
    assert list(frame["Assessment"]) == ["", "Likely equivalent"]
    assert list(frame["Time (ms)"]) == [12, 8]


def test_probe_results_prefers_the_error_text_as_details() -> None:
    outcomes = [
        {"id": "a", "actor": "x", "passed": True, "error": None, "message": "ok"},
        {"id": "b", "actor": "x", "passed": False, "error": "boom", "message": "m"},
    ]
    frame = tables.probe_results(outcomes).data
    assert list(frame["Result"]) == ["Pass", "Fail"]
    assert list(frame["Details"]) == ["ok", "boom"]
