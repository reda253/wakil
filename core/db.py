"""SQLite storage.  Owner: P3."""
import os
import sqlite3

DB_PATH = os.getenv("WAKIL_DB", "data/wakil.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone_masked TEXT,
    summary TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    local_id INTEGER NOT NULL,              -- Message["id"] from the parser
    timestamp TEXT,
    sender TEXT CHECK (sender IN ('me', 'client')),
    type TEXT CHECK (type IN ('text', 'voice')),
    content TEXT,
    transcript TEXT,
    audio_file TEXT
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    type TEXT CHECK (type IN ('task', 'promise', 'payment', 'deadline', 'question')),
    description TEXT,
    owner TEXT CHECK (owner IN ('me', 'client')),
    amount_mad REAL,
    due_date TEXT,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'done')),
    source_message_id INTEGER,              -- matches messages.local_id for this client
    confidence TEXT CHECK (confidence IN ('high', 'low'))
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_client(name, summary=None, phone_masked=None):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO clients (name, summary, phone_masked) VALUES (?, ?, ?)",
            (name, summary, phone_masked),
        )
        return cur.lastrowid


def save_messages(client_id, messages):
    with connect() as conn:
        conn.executemany(
            "INSERT INTO messages (client_id, local_id, timestamp, sender, type, content, transcript) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(client_id, m["id"], m["timestamp"], m["sender"], m["type"], m["content"], m.get("transcript"))
             for m in messages],
        )


def save_items(client_id, items):
    with connect() as conn:
        conn.executemany(
            "INSERT INTO items (client_id, type, description, owner, amount_mad, due_date, "
            "source_message_id, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(client_id, i["type"], i["description"], i["owner"], i.get("amount_mad"), i.get("due_date"),
              i["source_message_id"], i["confidence"]) for i in items],
        )


def get_clients():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY name")]


def get_messages(client_id):
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM messages WHERE client_id = ? ORDER BY local_id", (client_id,))]


def get_items(client_id=None, status="open"):
    q = "SELECT items.*, clients.name AS client_name FROM items JOIN clients ON clients.id = items.client_id WHERE 1=1"
    args = []
    if client_id is not None:
        q += " AND client_id = ?"
        args.append(client_id)
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY due_date IS NULL, due_date"
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, args)]


def get_source_message(client_id, local_id):
    with connect() as conn:
        r = conn.execute("SELECT * FROM messages WHERE client_id = ? AND local_id = ?",
                         (client_id, local_id)).fetchone()
        return dict(r) if r else None


def set_item_status(item_id, status):
    with connect() as conn:
        conn.execute("UPDATE items SET status = ? WHERE id = ?", (status, item_id))
