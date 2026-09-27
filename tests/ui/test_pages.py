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
    assert "dash_item_done_1" in [c.key for c in at.checkbox]  # the dashboard is the default page


DASH = str(ROOT / "pages" / "2_Dashboard.py")


def test_dashboard_renders_without_llm_calls(fake_backend):
    at = AppTest.from_file(DASH, default_timeout=20).run()
    assert not at.exception
    assert not at.title  # the hero headline replaces the page title
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
    html = " ".join(str(e.proto) for e in at.get("html"))
    assert "Nothing is late or due today." in html and "0 clients" in html


def test_dashboard_hero_says_one_client(fake_backend, monkeypatch):
    from core import db
    from tests.ui.conftest import CLIENTS
    monkeypatch.setattr(db, "get_clients", lambda: [dict(CLIENTS[0])])
    at = AppTest.from_file(DASH, default_timeout=20).run()
    html = " ".join(str(e.proto) for e in at.get("html"))
    assert "· 1 client<" in html


ORDERS = str(ROOT / "pages" / "5_Orders.py")


def _order_keys(at):
    return [c.key for c in at.checkbox]


def test_orders_page_lists_by_urgency(fake_backend):
    at = AppTest.from_file(ORDERS, default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Orders"
    assert _order_keys(at) == ["orders_item_done_6", "orders_item_done_2", "orders_item_done_3", "orders_item_done_7"]


def test_orders_page_filter_urgent(fake_backend):
    at = AppTest.from_file(ORDERS, default_timeout=20)
    at.session_state["orders_level"] = "urgent"
    at.run()
    assert _order_keys(at) == ["orders_item_done_6"]


def test_orders_page_filter_client(fake_backend):
    at = AppTest.from_file(ORDERS, default_timeout=20)
    at.session_state["orders_client"] = 1
    at.run()
    assert _order_keys(at) == ["orders_item_done_2", "orders_item_done_7"]


def test_orders_page_mark_delivered(fake_backend):
    at = AppTest.from_file(ORDERS, default_timeout=20).run()
    at.checkbox(key="orders_item_done_6").check().run()
    assert fake_backend["status_calls"] == [(6, "done")]


def test_orders_page_empty(fake_backend, monkeypatch):
    from core import db
    monkeypatch.setattr(db, "get_items", lambda client_id=None, status="open": [])
    at = AppTest.from_file(ORDERS, default_timeout=20).run()
    assert not at.exception and _order_keys(at) == []


CLIENT = str(ROOT / "pages" / "3_Client.py")


def test_client_page_renders_and_toggles(fake_backend):
    at = AppTest.from_file(CLIENT, default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Clients & history"
    at.checkbox(key="client_item_done_1").check().run()
    assert fake_backend["status_calls"] == [(1, "done")]


def test_client_page_preselects_imported_client(fake_backend):
    at = AppTest.from_file(CLIENT, default_timeout=20)
    at.session_state["client_id"] = 2
    at.run()
    assert at.selectbox(key="client_page_client").value == 2


def test_client_page_empty(fake_backend, monkeypatch):
    from core import db
    monkeypatch.setattr(db, "get_clients", lambda: [])
    at = AppTest.from_file(CLIENT, default_timeout=20).run()
    assert not at.exception


BRIEF_PAGE = str(ROOT / "pages" / "4_Brief_Reply.py")


def test_brief_page_flow(fake_backend):
    at = AppTest.from_file(BRIEF_PAGE, default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Brief & reply"
    at.button(key="page_gen").click().run()
    assert fake_backend["brief_calls"] == ["Ahmed Benali"]


def test_brief_page_llm_failure_shows_error(fake_backend, monkeypatch):
    from core import ai

    def boom(*args, **kwargs):
        raise RuntimeError("provider down")
    monkeypatch.setattr(ai, "make_brief", boom)
    at = AppTest.from_file(BRIEF_PAGE, default_timeout=20).run()
    at.button(key="page_gen").click().run()
    assert not at.exception
    assert at.error and "Could not prepare the brief" in at.error[0].value


def test_brief_panel_failed_draft_not_retried_on_rerun(fake_backend, monkeypatch):
    from core import ai
    calls = []

    def boom(brief, goal):
        calls.append(goal)
        raise RuntimeError("provider down")
    monkeypatch.setattr(ai, "draft_reply", boom)
    at = AppTest.from_function(_brief_app, default_timeout=15).run()
    at.button(key="t_gen").click().run()
    at.session_state["t_goal"] = "payment_reminder"
    at.run()
    assert at.error and "Could not write the draft" in at.error[0].value
    at.run()  # an unrelated rerun must not call the LLM again
    assert calls == ["payment_reminder"] and not at.exception


def _next_app():
    from core import db
    from ui.components import next_to_deliver
    from ui import viewmodel as vm
    next_to_deliver(vm.orders(db.get_items(), db.get_clients(), vm.today()))


def _next_empty_app():
    from ui.components import next_to_deliver
    next_to_deliver([])


def test_next_to_deliver_shows_three_and_count(fake_backend):
    at = AppTest.from_function(_next_app, default_timeout=15).run()
    assert not at.exception
    assert "1 more on the Orders page." in [c.value for c in at.caption]


def test_next_to_deliver_empty(fake_backend):
    at = AppTest.from_function(_next_empty_app, default_timeout=15).run()
    assert not at.exception and not at.caption


def test_dashboard_shows_next_to_deliver(fake_backend):
    at = AppTest.from_file(DASH, default_timeout=20).run()
    assert "1 more on the Orders page." in [c.value for c in at.caption]
