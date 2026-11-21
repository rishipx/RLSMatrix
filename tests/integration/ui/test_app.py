from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.integration

APP = Path(__file__).resolve().parents[3] / "src" / "rlsmatrix" / "ui" / "app.py"


def test_every_preset_runs_a_campaign() -> None:
    app = AppTest.from_file(str(APP), default_timeout=180).run()
    assert not app.exception
    for preset in app.selectbox(key="preset").options:
        app.selectbox(key="preset").select(preset).run()
        app.sidebar.button[0].click().run()
        assert not app.exception and not app.error, preset
        report = app.session_state["report"]
        assert report["baseline_ok"] and report["errors"] == 0


def test_an_invalid_suite_is_explained_not_run() -> None:
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.text_area(key="suite_yaml").set_value("actors: []\nprobes: []").run()
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert "not valid" in app.error[0].value
    assert "report" not in app.session_state
