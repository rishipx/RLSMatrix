from pathlib import Path

import pytest

from rlsmatrix import cli
from rlsmatrix.examples import DIRECTORY as EXAMPLES

pytestmark = pytest.mark.integration

EXAMPLE = EXAMPLES / "tenant_isolation"
BASE = [
    "run",
    "--bootstrap",
    str(EXAMPLE / "schema.sql"),
    "--manifest",
    str(EXAMPLE / "suite.yaml"),
    "--quiet",
]


def test_min_score_gate_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([*BASE, "--min-score", "71"]) == cli.EXIT_OK
    assert cli.main([*BASE, "--min-score", "72"]) == cli.EXIT_BELOW_THRESHOLD
    capsys.readouterr()


def test_report_formats_and_output_file(tmp_path: Path) -> None:
    target = tmp_path / "report.md"
    assert cli.main([*BASE, "--format", "markdown", "--output", str(target)]) == 0
    assert "**Mutation score: 71.4%**" in target.read_text(encoding="utf-8")


def test_failed_baseline_exits_with_its_own_code(tmp_path: Path) -> None:
    manifest = (EXAMPLE / "suite.yaml").read_text(encoding="utf-8")
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        manifest.replace("- [1]\n      - [2]", "- [99]"), encoding="utf-8"
    )
    argv = [
        "run",
        "--bootstrap",
        str(EXAMPLE / "schema.sql"),
        "--manifest",
        str(broken),
        "--quiet",
    ]
    assert cli.main(argv) == cli.EXIT_BASELINE_FAILED


def test_exclude_equivalent_gates_on_the_adjusted_score() -> None:
    # 71.4% raw, but both survivors are likely equivalent, so 100% adjusted.
    assert cli.main([*BASE, "--min-score", "95"]) == cli.EXIT_BELOW_THRESHOLD
    assert cli.main([*BASE, "--min-score", "95", "--exclude-equivalent"]) == cli.EXIT_OK
