"""Markdown campaign report, suited to pull-request comments and job summaries."""

from __future__ import annotations

from rlsmatrix.core.results import (
    BEHAVIOR_DIFFERS,
    LIKELY_EQUIVALENT,
    CampaignReport,
    MutationOutcome,
    format_score,
)

_LIKELY_EQUIVALENT_NOTE = (
    "**Likely equivalent.** Applying this change did not alter what any declared "
    "actor can read, update, delete or insert in your fixtures, so it is "
    "probably harmless here."
)
_BEHAVIOR_DIFFERS_NOTE = "Changes behavior, and no probe noticed."


def _assessment_lines(item: MutationOutcome) -> list[str]:
    if item.equivalence == LIKELY_EQUIVALENT:
        return [_LIKELY_EQUIVALENT_NOTE, ""]
    if item.equivalence == BEHAVIOR_DIFFERS:
        note = (
            f"**Changes behavior.** {item.difference}"
            if item.difference
            else _BEHAVIOR_DIFFERS_NOTE
        )
        return [note, ""]
    return []


def _failed_baseline(report: CampaignReport) -> list[str]:
    return [
        "The baseline failed. Fix these assertions before reading mutation results.",
        "",
        "| Probe | Actor | Details |",
        "|---|---|---|",
        *(
            f"| `{item.id}` | `{item.actor}` | {item.message} |"
            for item in report.baseline
            if not item.passed
        ),
    ]


def _summary(report: CampaignReport) -> list[str]:
    adjusted = (
        [
            "With likely-equivalent survivors left out "
            f"({report.likely_equivalent}), the score is "
            f"**{format_score(report.adjusted_score)}**.",
            "",
        ]
        if report.likely_equivalent
        else []
    )
    return [
        f"**Mutation score: {format_score(report.mutation_score)}** "
        f"({report.killed} killed, {report.survived} survived, "
        f"{report.errors} errors, {len(report.mutations)} mutations "
        f"in {report.duration_seconds:.1f}s)",
        "",
        *adjusted,
        "| Operator | Killed | Survived | Error |",
        "|---|---:|---:|---:|",
        *(
            f"| `{kind}` | {counts['KILLED']} | {counts['SURVIVED']} | {counts['ERROR']} |"
            for kind, counts in report.by_operator().items()
        ),
        "",
    ]


def _survivors(report: CampaignReport) -> list[str]:
    lines = ["## Surviving mutations", ""]
    survivors = [item for item in report.mutations if item.status == "SURVIVED"]
    if not survivors:
        lines.append("None. Every generated mutation was detected.")
    for item in survivors:
        lines += [
            f"### `{item.mutation.kind}` on `{item.mutation.target}`",
            "",
            item.mutation.description,
            "",
            *_assessment_lines(item),
            "```sql",
            item.mutation.sql,
            "```",
            *(
                []
                if item.equivalence == LIKELY_EQUIVALENT
                else [f"> {item.mutation.hint}"]
            ),
            "",
        ]
    return lines


def _errors(report: CampaignReport) -> list[str]:
    errored = [item for item in report.mutations if item.status == "ERROR"]
    if not errored:
        return []
    return [
        "",
        "## Errors",
        "",
        *(
            f"- `{item.mutation.kind}` on `{item.mutation.target}`: {item.error}"
            for item in errored
        ),
    ]


def render_markdown(report: CampaignReport) -> str:
    lines = [f"# RLSMatrix report: {report.suite_name}", ""]
    if not report.baseline_ok:
        lines += _failed_baseline(report)
    else:
        lines += _summary(report) + _survivors(report) + _errors(report)
    return "\n".join(lines) + "\n"
