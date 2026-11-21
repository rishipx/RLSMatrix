"""Command-line argument definitions."""

from __future__ import annotations

import argparse
from pathlib import Path

from rlsmatrix import __version__
from rlsmatrix.config import MAX_WORKERS, MIN_WORKERS


def _percent(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return number


def _workers(value: str) -> int:
    number = int(value)
    if not MIN_WORKERS <= number <= MAX_WORKERS:
        raise argparse.ArgumentTypeError(
            f"must be between {MIN_WORKERS} and {MAX_WORKERS}"
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rlsmatrix",
        description="Mutation testing for PostgreSQL Row-Level Security policies.",
    )
    parser.add_argument(
        "--version", action="version", version=f"rlsmatrix {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run a mutation campaign")
    run.add_argument(
        "--bootstrap", required=True, type=Path, help="schema and fixture SQL"
    )
    run.add_argument("--manifest", required=True, type=Path, help="YAML test manifest")
    run.add_argument(
        "--workers",
        type=_workers,
        help=f"parallel workers ({MIN_WORKERS}-{MAX_WORKERS})",
    )
    run.add_argument(
        "--operators",
        help=(
            "comma-separated operators or groups: core (default), predicate, shape, all"
        ),
    )
    run.add_argument(
        "--min-score",
        type=_percent,
        metavar="PERCENT",
        help="exit with status 1 if the mutation score is lower",
    )
    run.add_argument(
        "--exclude-equivalent",
        action="store_true",
        help="apply --min-score to the score that leaves out likely-equivalent survivors",
    )
    run.add_argument(
        "--allow-errors",
        action="store_true",
        help="do not fail when some mutations could not be evaluated",
    )
    run.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    run.add_argument("--output", type=Path, help="write the report to a file")
    run.add_argument("--quiet", action="store_true", help="no progress on stderr")

    validate = commands.add_parser(
        "validate", help="check a manifest without a database"
    )
    validate.add_argument("--manifest", required=True, type=Path)

    commands.add_parser("operators", help="list mutation operators")
    return parser
