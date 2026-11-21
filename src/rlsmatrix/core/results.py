"""Result and report data models, and mutation scoring."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from rlsmatrix import __version__
from rlsmatrix.mutations import Mutation

# How a surviving mutation is labelled; see core/equivalence.py.
LIKELY_EQUIVALENT = "likely_equivalent"
BEHAVIOR_DIFFERS = "behavior_differs"


def format_score(score: float | None) -> str:
    return "N/A" if score is None else f"{score:.1f}%"


@dataclass(slots=True)
class ProbeOutcome:
    id: str
    actor: str
    passed: bool
    expected_rows: list[list[Any]]
    actual_rows: list[list[Any]]
    expected_error: str | None = None
    error: str | None = None
    message: str = ""
    category: str = "ASSERTION"


@dataclass(slots=True)
class MutationOutcome:
    mutation: Mutation
    status: str
    probe_outcomes: list[ProbeOutcome]
    error: str | None = None
    duration_ms: float = 0.0
    equivalence: str | None = None  # survivors only: see core/equivalence.py
    difference: str | None = None

    @property
    def killed_by(self) -> list[str]:
        return [
            item.id
            for item in self.probe_outcomes
            if not item.passed and item.category != "RUNNER_ERROR"
        ]


@dataclass(slots=True)
class CampaignReport:
    suite_name: str
    started_at: str
    baseline_ok: bool
    policies: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    baseline: list[ProbeOutcome]
    mutations: list[MutationOutcome]
    duration_seconds: float = 0.0
    workers: int = 1
    operators: list[str] = field(default_factory=list)

    @property
    def killed(self) -> int:
        return sum(result.status == "KILLED" for result in self.mutations)

    @property
    def survived(self) -> int:
        return sum(result.status == "SURVIVED" for result in self.mutations)

    @property
    def errors(self) -> int:
        return sum(result.status == "ERROR" for result in self.mutations)

    @property
    def likely_equivalent(self) -> int:
        return sum(
            result.status == "SURVIVED" and result.equivalence == LIKELY_EQUIVALENT
            for result in self.mutations
        )

    @property
    def adjusted_score(self) -> float | None:
        """Score that leaves out survivors that changed nothing observable."""
        denominator = self.killed + self.survived - self.likely_equivalent
        if denominator == 0:
            return None
        return round(self.killed / denominator * 100, 1)

    @property
    def mutation_score(self) -> float | None:
        denominator = self.killed + self.survived
        if denominator == 0:
            return None
        return round(self.killed / denominator * 100, 1)

    def by_operator(self) -> dict[str, dict[str, int]]:
        grouped: dict[str, Counter[str]] = {}
        for item in self.mutations:
            grouped.setdefault(item.mutation.kind, Counter())[item.status] += 1
        return {
            kind: {
                "KILLED": counts["KILLED"],
                "SURVIVED": counts["SURVIVED"],
                "ERROR": counts["ERROR"],
            }
            for kind, counts in sorted(grouped.items())
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "rlsmatrix_version": __version__,
            "suite_name": self.suite_name,
            "started_at": self.started_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "workers": self.workers,
            "operators": self.operators,
            "baseline_ok": self.baseline_ok,
            "mutation_score": self.mutation_score,
            "adjusted_score": self.adjusted_score,
            "likely_equivalent": self.likely_equivalent,
            "killed": self.killed,
            "survived": self.survived,
            "errors": self.errors,
            "by_operator": self.by_operator(),
            "policies": self.policies,
            "tables": self.tables,
            "baseline": [asdict(item) for item in self.baseline],
            "mutations": [
                {
                    "mutation": asdict(item.mutation),
                    "status": item.status,
                    "killed_by": item.killed_by,
                    "hint": item.mutation.hint if item.status == "SURVIVED" else None,
                    "equivalence": item.equivalence,
                    "difference": item.difference,
                    "duration_ms": round(item.duration_ms, 1),
                    "probe_outcomes": [
                        asdict(outcome) for outcome in item.probe_outcomes
                    ],
                    "error": item.error,
                }
                for item in self.mutations
            ],
        }
