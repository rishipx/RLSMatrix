"""The GitHub Action delegates to scripts/action-run.sh, so test that directly."""

import os
import subprocess
from pathlib import Path

import pytest

from rlsmatrix.examples import DIRECTORY as EXAMPLES

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "action-run.sh"


def _run(tmp_path: Path, **inputs: str) -> tuple[int, str, str]:
    summary = tmp_path / "summary.md"
    output = tmp_path / "output.txt"
    env = {
        **os.environ,
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_OUTPUT": str(output),
        "INPUT_BOOTSTRAP": str(EXAMPLES / "shared_notes" / "schema.sql"),
        "INPUT_MANIFEST": str(EXAMPLES / "shared_notes" / "suite_first_draft.yaml"),
        **{f"INPUT_{key.upper()}": value for key, value in inputs.items()},
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=300
    )
    return (
        result.returncode,
        summary.read_text() if summary.exists() else "",
        output.read_text() if output.exists() else "",
    )


def test_publishes_the_report_and_the_score(tmp_path: Path) -> None:
    code, summary, output = _run(tmp_path, operators="core,predicate")
    assert code == 0
    assert "Mutation score: 81.8%" in summary
    assert "score=81.8" in output


def test_fails_when_the_score_is_below_the_threshold(tmp_path: Path) -> None:
    code, summary, output = _run(tmp_path, operators="core,predicate", min_score="90")
    assert code == 1
    assert "score=81.8" in output
    assert "Surviving mutations" in summary


def test_passes_when_the_threshold_is_met(tmp_path: Path) -> None:
    code, _, _ = _run(tmp_path, operators="core", min_score="100")
    assert code == 0


def test_a_bad_operator_fails_without_a_report(tmp_path: Path) -> None:
    code, summary, output = _run(tmp_path, operators="NOPE")
    assert code == 4
    assert summary == "" and output == ""
