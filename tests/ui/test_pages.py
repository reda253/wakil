from streamlit.testing.v1 import AppTest

from tests.ui.conftest import ROOT


def _card_app():
    from core import db
    from ui.components import item_card
    from ui.viewmodel import today
    item_card(db.get_items()[0], "Ahmed Benali", today(), key_prefix="t")


def _brief_app():
    from core import db
    from ui.components import brief_panel
    brief_panel(db.get_clients(), key="t")


def test_item_card_done_checkbox_updates_status(fake_backend):
    at = AppTest.from_function(_card_app, default_timeout=15).run()
    assert not at.exception
    at.checkbox(key="t_done_1").check().run()
    assert fake_backend["status_calls"] == [(1, "done")]


def test_brief_panel_no_llm_call_on_load(fake_backend):
    at = AppTest.from_function(_brief_app, default_timeout=15).run()
    assert not at.exception
    assert fake_backend["brief_calls"] == [] and fake_backend["draft_calls"] == []


def test_brief_panel_generates_brief_then_draft(fake_backend):
    at = AppTest.from_function(_brief_app, default_timeout=15).run()
    at.button(key="t_gen").click().run()
    assert fake_backend["brief_calls"] == ["Ahmed Benali"]
    at.session_state["t_goal"] = "payment_reminder"
    at.run()
    assert fake_backend["draft_calls"] == ["payment_reminder"]
    codes = [c.value for c in at.code]
    assert "WA draft for payment_reminder" in codes and "Email draft for payment_reminder" in codes
    at.run()  # rerun reuses the cached brief and draft
    assert fake_backend["brief_calls"] == ["Ahmed Benali"] and fake_backend["draft_calls"] == ["payment_reminder"]


def test_app_shell_runs_dashboard_by_default(fake_backend):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Dashboard"
