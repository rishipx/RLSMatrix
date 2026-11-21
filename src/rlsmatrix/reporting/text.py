"""Plain-text campaign report."""

from __future__ import annotations

from rlsmatrix.core.results import (
    BEHAVIOR_DIFFERS,
    LIKELY_EQUIVALENT,
    CampaignReport,
    MutationOutcome,
    format_score,
)

_MIN_KIND_WIDTH = 16
_TAGS = {
    LIKELY_EQUIVALENT: "  [likely equivalent]",
    BEHAVIOR_DIFFERS: "  [changes behavior]",
}


def _tag(item: MutationOutcome) -> str:
    return _TAGS.get(item.equivalence or "", "")


def render_text(report: CampaignReport) -> str:
    lines = [
        f"RLSMatrix: {report.suite_name}",
        f"baseline: {'passed' if report.baseline_ok else 'FAILED'}",
    ]
    if not report.baseline_ok:
        lines.extend(
            f"  FAIL {item.id} ({item.actor}): {item.message}"
            for item in report.baseline
            if not item.passed
        )
        return "\n".join(lines)

    lines.append(
        f"mutation score: {format_score(report.mutation_score)}  "
        f"({report.killed} killed, {report.survived} survived, "
        f"{report.errors} errors; {len(report.mutations)} mutations "
        f"in {report.duration_seconds:.1f}s)"
    )
    if report.likely_equivalent:
        lines.append(
            f"adjusted score: {format_score(report.adjusted_score)}  "
            f"(likely-equivalent survivors left out: {report.likely_equivalent})"
        )
    kind_width = max(
        [_MIN_KIND_WIDTH, *(len(item.mutation.kind) for item in report.mutations)]
    )
    for item in report.mutations:
        by = f"  <- {', '.join(item.killed_by)}" if item.killed_by else ""
        lines.append(
            f"  {item.status:<8} {item.mutation.kind:<{kind_width}} "
            f"{item.mutation.target}{by}{_tag(item)}"
        )
    return "\n".join(lines)
