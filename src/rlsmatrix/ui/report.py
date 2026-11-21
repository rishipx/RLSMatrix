"""Render a campaign report with native Streamlit components."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from rlsmatrix.core.results import format_score
from rlsmatrix.ui import tables


def _headline(report: dict[str, Any]) -> None:
    evaluated = report["killed"] + report["survived"]
    st.subheader(f"{report['killed']} of {evaluated} mutations detected")
    details = [
        f"Mutation score {format_score(report['mutation_score'])}",
        f"{report['survived']} survived",
        f"{report['errors']} could not be evaluated",
        *(
            [
                f"{format_score(report['adjusted_score'])} with likely-equivalent "
                f"survivors left out ({report['likely_equivalent']})"
            ]
            if report["likely_equivalent"]
            else []
        ),
        f"finished in {report['duration_seconds']} s on {report['workers']} workers",
    ]
    st.caption(", ".join(details) + ".")


def _survivors(report: dict[str, Any]) -> None:
    survivors = [item for item in report["mutations"] if item["status"] == "SURVIVED"]
    if not survivors:
        st.success("Every mutation was detected by at least one assertion.")
        return
    st.write(
        "Your tests did not notice these changes. Where the analysis found that "
        "a change alters what an actor can do, it is a real gap. A change marked "
        "likely equivalent altered nothing any declared actor can do in your "
        "fixtures, so it is probably harmless."
    )
    for item in survivors:
        assessment = tables.ASSESSMENTS.get(item["equivalence"] or "")
        label = tables.mutation_label(item)
        with st.expander(f"{label}: {assessment.lower()}" if assessment else label):
            if item["equivalence"] == "behavior_differs":
                st.warning(item["difference"])
            elif item["equivalence"] == "likely_equivalent":
                st.info(
                    "No actor can read, update, delete or insert differently after this change."
                )
            st.code(item["mutation"]["sql"], language="sql")
            if item["equivalence"] != "likely_equivalent":
                st.write(item["hint"])


def _coverage(report: dict[str, Any]) -> None:
    st.caption(
        f"Each row is one mutation and each column one probe. {tables.DETECTED} "
        "marks a probe that failed once the mutation was applied, which is how "
        "the mutation was detected."
    )
    st.dataframe(tables.coverage_matrix(report), hide_index=True, width="stretch")


def _mutations(report: dict[str, Any]) -> None:
    st.dataframe(tables.mutations_table(report), hide_index=True, width="stretch")
    items = report["mutations"]
    chosen = st.selectbox(
        "Inspect a mutation",
        options=range(len(items)),
        format_func=lambda index: tables.mutation_label(items[index]),
        key="inspected_mutation",
    )
    item = items[chosen]
    st.write(item["mutation"]["description"])
    st.code(item["mutation"]["sql"], language="sql")
    if item["error"]:
        st.error(item["error"])
    if item["probe_outcomes"]:
        st.dataframe(
            tables.probe_results(item["probe_outcomes"]),
            hide_index=True,
            width="stretch",
        )


def _policies(report: dict[str, Any]) -> None:
    st.write("Policies found in the schema")
    if report["policies"]:
        st.dataframe(report["policies"], hide_index=True, width="stretch")
    else:
        st.info(
            "The schema defines no row-level security policies, so there is nothing to mutate."
        )
    st.write("Tables")
    st.dataframe(report["tables"], hide_index=True, width="stretch")


def _failed_baseline(report: dict[str, Any]) -> None:
    st.error(
        "The baseline failed. Some assertions did not hold before any change "
        "was made, so mutation results would not mean anything. Fix these first."
    )
    st.dataframe(
        tables.probe_results(report["baseline"]), hide_index=True, width="stretch"
    )


def render_report(report: dict[str, Any]) -> None:
    st.divider()
    st.header("Results")
    if not report["baseline_ok"]:
        _failed_baseline(report)
        return

    _headline(report)
    st.download_button(
        "Download JSON report",
        data=json.dumps(report, indent=2, default=str),
        file_name="rlsmatrix-report.json",
        mime="application/json",
    )
    if not report["mutations"]:
        st.info("No mutations apply to this schema.")
        return

    survivors = sum(item["status"] == "SURVIVED" for item in report["mutations"])
    survivors_tab, coverage_tab, mutations_tab, policies_tab = st.tabs(
        [f"Survivors ({survivors})", "Coverage matrix", "All mutations", "Policies"]
    )
    with survivors_tab:
        _survivors(report)
    with coverage_tab:
        _coverage(report)
    with mutations_tab:
        _mutations(report)
    with policies_tab:
        _policies(report)
