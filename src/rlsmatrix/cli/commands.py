"""Implementations of the ``run``, ``validate`` and ``operators`` commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from rlsmatrix.cli.exit_codes import (
    EXIT_BASELINE_FAILED,
    EXIT_BELOW_THRESHOLD,
    EXIT_OK,
    EXIT_RUN_ERROR,
)
from rlsmatrix.core.results import CampaignReport, format_score
from rlsmatrix.mutations import CORE_OPERATORS, OPERATORS, SHAPE_OPERATORS


class CliError(Exception):
    """A user-facing failure that maps to EXIT_RUN_ERROR."""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(f"cannot read {path}: {exc.strerror}") from exc


def _describe(exc: ValidationError) -> str:
    return "\n".join(
        f"  {' > '.join(str(part) for part in issue['loc'])}: {issue['msg']}"
        for issue in exc.errors()
    )


def _emit(text: str, destination: Path | None) -> None:
    if destination is not None:
        destination.write_text(text + "\n", encoding="utf-8")
        return
    try:
        print(text)
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader (for example `head`) went away. Keep going so the exit
        # code still reflects the result.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


def _render(report: CampaignReport, fmt: str) -> str:
    from rlsmatrix.reporting import render_markdown, render_text

    if fmt == "json":
        return json.dumps(report.to_dict(), indent=2, default=str)
    if fmt == "markdown":
        return render_markdown(report)
    return render_text(report)


def _exit_code(report: CampaignReport, args: argparse.Namespace) -> int:
    if not report.baseline_ok:
        return EXIT_BASELINE_FAILED
    if report.errors and not args.allow_errors:
        print(f"{report.errors} mutation(s) could not be evaluated.", file=sys.stderr)
        return EXIT_RUN_ERROR
    score = report.adjusted_score if args.exclude_equivalent else report.mutation_score
    if args.min_score is not None and (score is None or score < args.min_score):
        print(
            f"Mutation score {format_score(score)} is below the required "
            f"{args.min_score:.1f}%.",
            file=sys.stderr,
        )
        return EXIT_BELOW_THRESHOLD
    return EXIT_OK


def run_command(args: argparse.Namespace) -> int:
    from rlsmatrix.core.campaign import run_mutation_campaign
    from rlsmatrix.manifest import load_test_suite

    operators = args.operators.split(",") if args.operators else None
    progress = None if args.quiet else lambda message: print(message, file=sys.stderr)
    try:
        suite = load_test_suite(_read_text(args.manifest))
        report = run_mutation_campaign(
            _read_text(args.bootstrap),
            suite,
            progress,
            workers=args.workers,
            operators=operators,
        )
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUN_ERROR
    except ValidationError as exc:
        print(f"Manifest is invalid:\n{_describe(exc)}", file=sys.stderr)
        return EXIT_RUN_ERROR
    except Exception as exc:
        print(f"Campaign could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_RUN_ERROR

    try:
        _emit(_render(report, args.format), args.output)
    except OSError as exc:
        print(f"error: cannot write {args.output}: {exc.strerror}", file=sys.stderr)
        return EXIT_RUN_ERROR
    return _exit_code(report, args)


def validate_command(args: argparse.Namespace) -> int:
    from rlsmatrix.manifest import load_test_suite
    from rlsmatrix.manifest.validation import validate_suite_probes

    try:
        suite = load_test_suite(_read_text(args.manifest))
        validate_suite_probes(suite)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUN_ERROR
    except ValidationError as exc:
        print(f"Manifest is invalid:\n{_describe(exc)}", file=sys.stderr)
        return EXIT_RUN_ERROR
    except (ValueError, yaml.YAMLError) as exc:
        print(f"Manifest is invalid: {exc}", file=sys.stderr)
        return EXIT_RUN_ERROR
    print(f"OK: {suite.name}, {len(suite.actors)} actors, {len(suite.probes)} probes")
    return EXIT_OK


def operators_command(_: argparse.Namespace) -> int:
    lines = []
    for name, description in OPERATORS.items():
        group = (
            "core"
            if name in CORE_OPERATORS
            else "shape"
            if name in SHAPE_OPERATORS
            else "predicate"
        )
        lines.append(f"{name:<26} {group:<10} {description}")
    lines += [
        "",
        "Runs core by default. Use --operators all, or name operators/groups.",
    ]
    _emit("\n".join(lines), None)
    return EXIT_OK
