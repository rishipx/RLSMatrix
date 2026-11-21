"""The ``rlsmatrix`` command-line interface."""

from __future__ import annotations

from collections.abc import Sequence

from rlsmatrix.cli.commands import operators_command, run_command, validate_command
from rlsmatrix.cli.exit_codes import (
    EXIT_BASELINE_FAILED,
    EXIT_BELOW_THRESHOLD,
    EXIT_OK,
    EXIT_RUN_ERROR,
)
from rlsmatrix.cli.parser import build_parser

__all__ = [
    "EXIT_BASELINE_FAILED",
    "EXIT_BELOW_THRESHOLD",
    "EXIT_OK",
    "EXIT_RUN_ERROR",
    "build_parser",
    "main",
]

_COMMANDS = {
    "run": run_command,
    "validate": validate_command,
    "operators": operators_command,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args)
