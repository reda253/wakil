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


DASH = str(ROOT / "pages" / "2_Dashboard.py")


def test_dashboard_renders_without_llm_calls(fake_backend):
    at = AppTest.from_file(DASH, default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Dashboard"
    assert fake_backend["brief_calls"] == []


def test_dashboard_breakdowns_live_in_details(fake_backend):
    at = AppTest.from_file(DASH, default_timeout=20).run()
    md = [m.value for m in at.markdown]
    assert "**1** made by you · **0** made by clients" in md
    assert "**1** urgent · **1** high · **1** normal · **1** low" in md
    assert not any("webhook" in m.lower() for m in md)


def test_dashboard_done_checkbox(fake_backend):
    at = AppTest.from_file(DASH, default_timeout=20).run()
    at.checkbox(key="dash_item_done_2").check().run()
    assert fake_backend["status_calls"] == [(2, "done")]


def test_dashboard_draft_reminder_prefills_brief(fake_backend):
    at = AppTest.from_file(DASH, default_timeout=20).run()
    at.button(key="owed_0_draft").click().run()
    assert fake_backend["brief_calls"] == ["Ahmed Benali"]
    assert fake_backend["draft_calls"] == ["payment_reminder"]
    assert "WA draft for payment_reminder" in [c.value for c in at.code]


def test_dashboard_empty_backend(fake_backend, monkeypatch):
    from core import db
    monkeypatch.setattr(db, "get_clients", lambda: [])
    monkeypatch.setattr(db, "get_items", lambda client_id=None, status="open": [])
    monkeypatch.setattr(db, "get_money_owed", lambda: [])
    at = AppTest.from_file(DASH, default_timeout=20).run()
    assert not at.exception
