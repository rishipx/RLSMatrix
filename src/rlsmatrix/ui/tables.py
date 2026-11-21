"""Shape a campaign report (as a dict) into tables for display."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.io.formats.style import Styler

DETECTED = "✓"

ASSESSMENTS = {
    "likely_equivalent": "Likely equivalent",
    "behavior_differs": "Changes behavior",
}

_RESULT_COLORS = {
    "Killed": "rgba(26, 127, 75, 0.20)",
    "Survived": "rgba(179, 64, 42, 0.22)",
    "Error": "rgba(128, 128, 128, 0.22)",
    "Pass": "rgba(26, 127, 75, 0.20)",
    "Fail": "rgba(179, 64, 42, 0.22)",
}
_DETECTED_STYLE = "background-color: rgba(31, 111, 139, 0.28); font-weight: 600"


def _result_style(value: object) -> str:
    color = _RESULT_COLORS.get(str(value))
    return f"background-color: {color}; font-weight: 600" if color else ""


def _detected_style(value: object) -> str:
    return _DETECTED_STYLE if value == DETECTED else ""


def mutation_label(item: dict[str, Any]) -> str:
    mutation = item["mutation"]
    return f"{mutation['kind']} on {mutation['target']}"


def mutations_table(report: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Operator": item["mutation"]["kind"],
            "Target": item["mutation"]["target"],
            "Result": item["status"].title(),
            "Assessment": ASSESSMENTS.get(item["equivalence"] or "", ""),
            "Detected by": ", ".join(item["killed_by"]),
            "Time (ms)": round(item["duration_ms"]),
        }
        for item in report["mutations"]
    )


def coverage_matrix(report: dict[str, Any]) -> Styler:
    """One row per mutation, one column per probe; ✓ means the probe failed."""
    probes = [probe["id"] for probe in report["baseline"]]
    rows = []
    for item in report["mutations"]:
        detected = set(item["killed_by"])
        rows.append(
            {
                "Operator": item["mutation"]["kind"],
                "Target": item["mutation"]["target"],
                "Result": item["status"].title(),
                **{probe: DETECTED if probe in detected else "" for probe in probes},
            }
        )
    frame = pd.DataFrame(rows, columns=["Operator", "Target", "Result", *probes])
    styler = frame.style.map(_result_style, subset=["Result"])
    if probes:
        styler = styler.map(_detected_style, subset=probes)
    return styler


def probe_results(outcomes: list[dict[str, Any]]) -> Styler:
    frame = pd.DataFrame(
        {
            "Probe": item["id"],
            "Actor": item["actor"],
            "Result": "Pass" if item["passed"] else "Fail",
            "Details": item["error"] or item["message"],
        }
        for item in outcomes
    )
    return frame.style.map(_result_style, subset=["Result"])
