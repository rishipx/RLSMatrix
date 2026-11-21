from pathlib import Path

import pytest

from rlsmatrix import cli
from rlsmatrix.examples import DIRECTORY as EXAMPLES


def test_lists_operators(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["operators"]) == cli.EXIT_OK
    output = capsys.readouterr().out
    assert "DROP_POLICY" in output
    assert "DROP_CLAUSE" in output
    assert "predicate" in output


def test_validates_every_bundled_manifest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifests = sorted(EXAMPLES.glob("*/suite*.yaml"))
    assert manifests
    for manifest in manifests:
        assert (manifest.parent / "schema.sql").is_file(), manifest.parent.name
        assert cli.main(["validate", "--manifest", str(manifest)]) == cli.EXIT_OK
    assert "OK:" in capsys.readouterr().out


def test_validate_reports_disallowed_probe_sql(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "m.yaml"
    manifest.write_text(
        "actors:\n  - {id: a, role: authenticated}\n"
        "probes:\n  - {id: p, actor: a, sql: 'DROP TABLE x'}\n",
        encoding="utf-8",
    )
    assert cli.main(["validate", "--manifest", str(manifest)]) == cli.EXIT_RUN_ERROR
    assert "not allowed" in capsys.readouterr().err


def test_unreadable_input_is_a_run_error_not_a_threshold_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit status 1 is reserved for 'score below --min-score'."""
    code = cli.main(["validate", "--manifest", str(tmp_path / "missing.yaml")])
    assert code == cli.EXIT_RUN_ERROR
    assert "cannot read" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["-1", "101", "abc"])
def test_min_score_must_be_a_percentage(bad: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(
            ["run", "--bootstrap", "a.sql", "--manifest", "m.yaml", "--min-score", bad]
        )
    assert exit_info.value.code == 2


@pytest.mark.parametrize("bad", ["0", "17"])
def test_workers_must_be_in_range(bad: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(
            ["run", "--bootstrap", "a.sql", "--manifest", "m.yaml", "--workers", bad]
        )
    assert exit_info.value.code == 2


def test_operators_listing_survives_a_closed_pipe(monkeypatch) -> None:
    def broken(*_args, **_kwargs):
        raise BrokenPipeError

    monkeypatch.setattr("builtins.print", broken)
    monkeypatch.setattr("os.dup2", lambda *_: None)
    assert cli.main(["operators"]) == cli.EXIT_OK


def test_unwritable_output_is_reported_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import rlsmatrix.core.campaign as campaign
    from rlsmatrix.core.results import CampaignReport

    report = CampaignReport(
        suite_name="S",
        started_at="2026-01-01T00:00:00+00:00",
        baseline_ok=True,
        policies=[],
        tables=[],
        baseline=[],
        mutations=[],
    )
    monkeypatch.setattr(campaign, "run_mutation_campaign", lambda *_a, **_k: report)
    manifest = next(EXAMPLES.glob("tenant_isolation/suite.yaml"))
    schema = manifest.parent / "schema.sql"
    code = cli.main(
        [
            "run",
            "--bootstrap",
            str(schema),
            "--manifest",
            str(manifest),
            "--quiet",
            "--output",
            str(tmp_path / "missing" / "report.md"),
        ]
    )
    assert code == cli.EXIT_RUN_ERROR
    assert "cannot write" in capsys.readouterr().err
