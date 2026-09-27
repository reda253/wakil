"""Shared test data and a fake backend for UI tests.  Owner: D4."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TODAY = "2026-09-27"

CLIENTS = [
    {"id": 1, "name": "Ahmed Benali", "phone": "+212600000001"},
    {"id": 2, "name": "Sara", "phone": None},
]

MESSAGES = [
    {"id": 10, "client_id": 1, "timestamp": "2026-09-20T10:05", "sender": "client", "type": "text",
     "content": "I want a kitchen <b>now</b>", "transcript": None, "source": "export"},
    {"id": 11, "client_id": 1, "timestamp": "2026-09-21T18:40", "sender": "client", "type": "voice",
     "content": "PTT-1.opus", "transcript": "I'll send the deposit Friday", "source": "whatsapp"},
    {"id": 20, "client_id": 2, "timestamp": "2026-09-22T09:00", "sender": "owner", "type": "text",
     "content": "Merci Sara", "transcript": None, "source": "export"},
]

ITEMS = [
    # payment owed by client 1, overdue
    {"id": 1, "client_id": 1, "type": "payment", "description": "Deposit 7,500 MAD", "owner": "client",
     "amount_mad": 7500.0, "due_date": "2026-09-25", "source_message_id": 11, "confidence": "high", "status": "open"},
    # order: deadline due today, low confidence -> urgency high
    {"id": 2, "client_id": 1, "type": "deadline", "description": "Deliver kitchen", "owner": "me",
     "amount_mad": None, "due_date": "2026-09-27", "source_message_id": 10, "confidence": "low", "status": "open"},
    # order: promise in 5 days -> urgency normal
    {"id": 3, "client_id": 2, "type": "promise", "description": "Send fabric samples", "owner": "me",
     "amount_mad": None, "due_date": "2026-10-02", "source_message_id": 20, "confidence": "high", "status": "open"},
    # client question, no date (not an order)
    {"id": 4, "client_id": 2, "type": "question", "description": "Which colour?", "owner": "client",
     "amount_mad": None, "due_date": None, "source_message_id": 20, "confidence": "high", "status": "open"},
    # done payment (ignored everywhere open-only)
    {"id": 5, "client_id": 2, "type": "payment", "description": "Balance 1,200 MAD", "owner": "client",
     "amount_mad": 1200.0, "due_date": "2026-10-05", "source_message_id": 20, "confidence": "high", "status": "done"},
    # order: task overdue -> urgency urgent
    {"id": 6, "client_id": 2, "type": "task", "description": "Cut fabric for curtains", "owner": "me",
     "amount_mad": None, "due_date": "2026-09-26", "source_message_id": 20, "confidence": "high", "status": "open"},
    # order: task in 23 days -> urgency low
    {"id": 7, "client_id": 1, "type": "task", "description": "Install kitchen handles", "owner": "me",
     "amount_mad": None, "due_date": "2026-10-20", "source_message_id": 10, "confidence": "high", "status": "open"},
]

OWED = [{"client": "Ahmed Benali", "amount_mad": 7500.0}]

BRIEF = ("Status: kitchen order\nMy promises: deliver today\nClient's promises: deposit Friday\n"
         "Money owed: 7,500 MAD\nNext step: call about deposit")


def open_items():
    return [dict(i) for i in ITEMS if i["status"] == "open"]


@pytest.fixture
def fake_backend(monkeypatch):
    """Replace core.db and core.ai with in-memory fakes. Returns a dict recording calls."""
    from core import ai, db

    monkeypatch.setenv("WAKIL_TODAY", TODAY)
    state = {"items": copy.deepcopy(ITEMS), "status_calls": [], "brief_calls": [], "draft_calls": []}

    def get_items(client_id=None, status="open"):
        return [dict(i) for i in state["items"]
                if (client_id is None or i["client_id"] == client_id) and (status is None or i["status"] == status)]

    def get_messages(client_id, limit=None):
        msgs = [dict(m) for m in MESSAGES if m["client_id"] == client_id]
        return msgs[-limit:] if limit else msgs

    def get_message(ref, client_id=None):
        return next((dict(m) for m in MESSAGES
                     if m["id"] == ref and (client_id is None or m["client_id"] == client_id)), None)

    def set_item_status(item_id, status):
        state["status_calls"].append((item_id, status))
        for i in state["items"]:
            if i["id"] == item_id:
                i["status"] = status

    def make_brief(client_name, items, recent_messages):
        state["brief_calls"].append(client_name)
        return BRIEF

    def draft_reply(brief, goal):
        state["draft_calls"].append(goal)
        return {"whatsapp": f"WA draft for {goal}", "email": f"Email draft for {goal}"}

    monkeypatch.setattr(db, "get_clients", lambda: [dict(c) for c in CLIENTS])
    monkeypatch.setattr(db, "get_client", lambda id: next((dict(c) for c in CLIENTS if c["id"] == id), None))
    monkeypatch.setattr(db, "get_items", get_items)
    monkeypatch.setattr(db, "get_messages", get_messages)
    monkeypatch.setattr(db, "get_message", get_message)
    monkeypatch.setattr(db, "set_item_status", set_item_status)
    monkeypatch.setattr(db, "get_money_owed", lambda: [dict(o) for o in OWED])
    monkeypatch.setattr(ai, "make_brief", make_brief)
    monkeypatch.setattr(ai, "draft_reply", draft_reply)
    return state
