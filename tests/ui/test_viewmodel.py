from datetime import date

from tests.ui.conftest import CLIENTS, ITEMS, OWED, open_items
from ui import viewmodel as vm

T = date(2026, 9, 27)


def test_today_env_override(monkeypatch):
    monkeypatch.setenv("WAKIL_TODAY", "2026-01-15")
    assert vm.today() == date(2026, 1, 15)
    monkeypatch.setenv("WAKIL_TODAY", "garbage")
    assert vm.today() == date.today()


def test_classify_due():
    assert vm.classify_due("2026-09-25", T) == "overdue"
    assert vm.classify_due("2026-09-27", T) == "today"
    assert vm.classify_due("2026-10-02", T) == "upcoming"
    assert vm.classify_due(None, T) == "none"
    assert vm.classify_due("next week", T) == "none"


def test_due_label():
    assert vm.due_label("2026-09-25", T) == "2 days late"
    assert vm.due_label("2026-09-26", T) == "1 day late"
    assert vm.due_label("2026-09-27", T) == "Due today"
    assert vm.due_label("2026-09-28", T) == "Due tomorrow"
    assert vm.due_label("2026-10-02", T) == "Due in 5 days"


def test_due_label_invalid():
    assert vm.due_label(None, T) == "No due date"
    assert vm.due_label("", T) == "No due date"
    assert vm.due_label("vendredi", T) == "No due date"


def test_fmt_mad():
    assert vm.fmt_mad(7500) == "7,500 MAD"
    assert vm.fmt_mad(7500.4) == "7,500 MAD"
    assert vm.fmt_mad("1200") == "1,200 MAD"


def test_fmt_mad_invalid():
    assert vm.fmt_mad(None) == "-"
    assert vm.fmt_mad("1.5k") == "-"


def test_initials():
    assert vm.initials("ahmed benali") == "AB"
    assert vm.initials("Sara") == "S"
    assert vm.initials("") == "?"
    assert vm.initials(None) == "?"


def test_bucket_counts_partition():
    assert vm.bucket_counts(open_items(), T) == {"all": 6, "overdue": 2, "today": 1, "upcoming": 3}


def test_filter_items_order():
    assert [i["id"] for i in vm.filter_items(open_items(), "all", T)] == [1, 6, 2, 3, 7, 4]
    assert [i["id"] for i in vm.filter_items(open_items(), "upcoming", T)] == [3, 7, 4]
    assert [i["id"] for i in vm.filter_items(open_items(), "overdue", T)] == [1, 6]
    assert vm.filter_items([], "today", T) == []


def test_urgency():
    assert vm.urgency("2026-09-26", T) == "urgent"
    assert vm.urgency("2026-09-27", T) == "high"
    assert vm.urgency("2026-09-28", T) == "high"
    assert vm.urgency("2026-09-29", T) == "normal"
    assert vm.urgency("2026-10-04", T) == "normal"
    assert vm.urgency("2026-10-05", T) == "low"
    assert vm.urgency(None, T) == "low"
    assert vm.urgency("soon", T) == "low"


def test_client_owes_ignores_done_and_other_owner():
    assert vm.client_owes(ITEMS, 1) == 7500.0
    assert vm.client_owes(ITEMS, 2) == 0.0


def test_orders_selection_and_order():
    rows = vm.orders(open_items(), CLIENTS, T)
    assert [r["item"]["id"] for r in rows] == [6, 2, 3, 7]
    assert [r["urgency"] for r in rows] == ["urgent", "high", "normal", "low"]
    assert rows[0]["client"] == "Sara" and rows[0]["client_owes"] == 0.0
    assert rows[1]["client"] == "Ahmed Benali" and rows[1]["client_owes"] == 7500.0
    assert rows[1]["due_label"] == "Due today"


def test_urgency_counts():
    rows = vm.orders(open_items(), CLIENTS, T)
    assert vm.urgency_counts(rows) == {"all": 4, "urgent": 1, "high": 1, "normal": 1, "low": 1}
    assert vm.urgency_counts([]) == {"all": 0, "urgent": 0, "high": 0, "normal": 0, "low": 0}


def test_dashboard_metrics():
    assert vm.dashboard_metrics(open_items(), OWED, CLIENTS, T) == {
        "owed_total": 7500.0, "owed_clients": 1, "owed_overdue": 7500.0,
        "open": 6, "overdue": 2, "today": 1,
        "orders": 4, "orders_urgent": 1,
        "promises": 1, "promises_mine": 1, "promises_client": 0,
        "to_verify": 1,
    }


def test_dashboard_metrics_empty():
    m = vm.dashboard_metrics([], [], [], T)
    assert m["owed_total"] == 0 and m["open"] == 0 and m["orders"] == 0 and m["to_verify"] == 0


def test_owed_rows():
    rows = vm.owed_rows(OWED, open_items(), CLIENTS, T)
    assert len(rows) == 1
    r = rows[0]
    assert r["client"] == "Ahmed Benali" and r["client_id"] == 1 and r["amount_mad"] == 7500.0
    assert r["overdue"] is True and r["due_label"] == "2 days late" and r["initials"] == "AB"
    assert r["item"]["id"] == 1 and r["description"] == "Deposit 7,500 MAD"
    assert "tone" not in r


def test_owed_rows_unknown_client_and_zero_amount():
    owed = [{"client": "Ghost", "amount_mad": 100}, {"client": "Sara", "amount_mad": 0}]
    rows = vm.owed_rows(owed, open_items(), CLIENTS, T)
    assert [r["client"] for r in rows] == ["Ghost"]
    assert rows[0]["client_id"] is None and rows[0]["item"] is None and rows[0]["due_label"] == "No due date"


def test_parse_brief():
    text = "1. Status: kitchen order\n- My promises: deliver today\n\nJust call him"
    assert vm.parse_brief(text) == [("Status", "kitchen order"), ("My promises", "deliver today"),
                                    ("", "Just call him")]
    assert vm.parse_brief("") == [] and vm.parse_brief(None) == []


def test_whatsapp_link():
    assert vm.whatsapp_link("Hi there & bye", "+212 600-000001") == \
        "https://wa.me/212600000001?text=Hi%20there%20%26%20bye"
    assert vm.whatsapp_link("Hi", None) == "https://wa.me/?text=Hi"


def test_whatsapp_link_masked_phone():
    assert vm.whatsapp_link("Hi", "+212 6** ** ** 12") == "https://wa.me/?text=Hi"
    assert vm.whatsapp_link("Hi", "123") == "https://wa.me/?text=Hi"
