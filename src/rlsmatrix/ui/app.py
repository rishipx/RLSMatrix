"""Streamlit page: choose an example, edit inputs and run a campaign."""

from __future__ import annotations

import streamlit as st
import yaml
from pydantic import ValidationError

from rlsmatrix.core.campaign import run_mutation_campaign
from rlsmatrix.manifest import load_test_suite
from rlsmatrix.mutations import CORE_OPERATORS, OPERATORS
from rlsmatrix.ui.presets import DEFAULT_PRESET, PRESETS, load_preset
from rlsmatrix.ui.report import render_report


def _apply_preset() -> None:
    schema, manifest = load_preset(st.session_state["preset"])
    st.session_state["bootstrap_sql"] = schema
    st.session_state["suite_yaml"] = manifest
    st.session_state.pop("report", None)


def _run(
    bootstrap_sql: str, suite_yaml: str, operators: list[str], workers: int
) -> None:
    st.session_state.pop("report", None)
    try:
        if not operators:
            raise ValueError("Choose at least one mutation operator.")
        suite = load_test_suite(suite_yaml)
        with st.status("Running campaign", expanded=True) as status:
            bar = st.progress(0.0)

            def update(done: int, total: int) -> None:
                bar.progress(done / total)

            report = run_mutation_campaign(
                bootstrap_sql,
                suite,
                progress=lambda message: status.update(label=message),
                workers=workers,
                operators=operators,
                on_progress=update,
            )
            status.update(label="Campaign finished", state="complete", expanded=False)
        st.session_state["report"] = report.to_dict()
    except ValidationError as exc:
        st.error("The test suite is not valid. Fix these fields and run again:")
        for issue in exc.errors():
            location = " > ".join(str(part) for part in issue["loc"])
            st.write(f"- `{location}`: {issue['msg']}")
    except (ValueError, yaml.YAMLError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"The campaign could not run: {type(exc).__name__}: {exc}")


def main() -> None:
    st.set_page_config(page_title="RLSMatrix", layout="wide")

    if "preset" not in st.session_state:
        st.session_state["preset"] = DEFAULT_PRESET
    if "bootstrap_sql" not in st.session_state:
        _apply_preset()

    with st.sidebar:
        st.title("RLSMatrix")
        st.caption("Row-Level Security mutation testing")
        st.selectbox("Example", list(PRESETS), key="preset", on_change=_apply_preset)
        operators = st.multiselect(
            "Mutation operators",
            options=list(OPERATORS),
            default=[name for name in OPERATORS if name in CORE_OPERATORS],
            format_func=lambda name: name.replace("_", " ").capitalize(),
            help="\n".join(f"{name}: {text}" for name, text in OPERATORS.items()),
        )
        workers = st.slider("Parallel workers", min_value=1, max_value=8, value=4)
        run_clicked = st.button("Run campaign", type="primary", width="stretch")
        st.caption(
            "Runs a baseline first, and applies mutations only if every assertion "
            "passes. The schema runs as the sandbox administrator, so use trusted "
            "SQL only."
        )

    st.header("Schema and tests")
    schema_tab, suite_tab = st.tabs(["Schema SQL", "Test suite (YAML)"])
    with schema_tab:
        st.caption(
            "Runs once in a disposable database. It must create the roles, tables, "
            "policies and fixture rows."
        )
        st.text_area(
            "Schema SQL", key="bootstrap_sql", height=380, label_visibility="collapsed"
        )
    with suite_tab:
        st.caption(
            "The actors, the probes they run, and the results each probe must give."
        )
        st.text_area(
            "Test suite", key="suite_yaml", height=380, label_visibility="collapsed"
        )

    if run_clicked:
        _run(
            st.session_state["bootstrap_sql"],
            st.session_state["suite_yaml"],
            operators,
            workers,
        )

    report = st.session_state.get("report")
    if report:
        render_report(report)


if __name__ == "__main__":
    main()
