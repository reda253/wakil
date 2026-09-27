"""Storage.  Owner: D3.

SQLAlchemy on DATABASE_URL (Guepard Postgres, or sqlite:///wakil.db fallback).
Tables: clients(id, name, phone), messages, items matching core/contracts.py.
"""
from core import parser, ai

# STUB data: replace every function with real DB queries
_CLIENTS = [{"id": 1, "name": "Ahmed", "phone": None}]
_MESSAGES = [dict(m, client_id=1) for m in parser.parse_export("", "")[1]]
_ITEMS = [dict(it, id=n, client_id=1) for n, it in enumerate(ai.extract_items("Ahmed", [])["items"], 1)]


def get_clients():
    return _CLIENTS


def get_client(id):
    return next((c for c in _CLIENTS if c["id"] == id), None)


def get_or_create_client(name, phone=None):
    return _CLIENTS[0]["id"]


def get_items(client_id=None, status="open"):
    return [i for i in _ITEMS
            if (client_id is None or i["client_id"] == client_id) and (status is None or i["status"] == status)]


def get_messages(client_id, limit=None):
    msgs = [m for m in _MESSAGES if m["client_id"] == client_id]
    return msgs[-limit:] if limit else msgs


def get_message(message_id):
    return next((m for m in _MESSAGES if m["id"] == message_id), None)


def set_item_status(item_id, status):
    for i in _ITEMS:
        if i["id"] == item_id:
            i["status"] = status


def get_money_owed():
    """Return list[{"client", "amount_mad"}]."""
    return [{"client": "Ahmed", "amount_mad": 7500.0}]
