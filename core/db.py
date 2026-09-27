"""Storage.  Owner: D3.

sqlite:///wakil.db by default.  Tables: clients(id, name, phone), messages, items,
matching core/contracts.py.

Two id spaces, and confusing them is the classic bug here:
  * messages.id        the SQLite row primary key, global and ever-growing
  * messages.local_id  the per-chat sequential id the parser assigned, and the value
                       every Item.source_message_id points at ("view source")
Every read helper that a source_message_id can reach accepts either, so callers on
either side of the contract still get the right row.
"""
import contextlib
import os
import sqlite3

from core.parser import mask_phone

# D3 decision: sqlite stays.  If a hosted Postgres URL ever lands, the engine is the
# only thing that changes here - every function below already goes through _conn().
DB_PATH = os.getenv("WAKIL_DB") or "wakil.db"

_SENDER_ALIASES = {"owner": "me", "me": "me", "client": "client"}
_SENDERS = ("me", "client")


def _norm_sender(value):
    """Accept both vocabularies ('owner' from contracts.py, 'me' from the old code)."""
    return _SENDER_ALIASES.get((value or "").strip().lower(), "client")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@contextlib.contextmanager
def _conn():
    conn = connect()
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _rebuild_schema(conn):
    """Drop all three tables.

    Only ever called when _has_schema() has already decided the schema is unusable,
    and the reason is usually a CHECK constraint: SQLite cannot ALTER one, so the
    previous messages.sender = ('owner','client') table would reject every insert of
    'me' no matter what CREATE TABLE IF NOT EXISTS does.  These files are local
    scratch (gitignored) and the chat export is the real source of truth, so
    rebuilding is both the only option and the correct one.
    """
    conn.executescript(
        "DROP TABLE IF EXISTS items;"
        "DROP TABLE IF EXISTS messages;"
        "DROP TABLE IF EXISTS clients;")
    print(f"[db] '{DB_PATH}' had an older schema and was rebuilt. "
          "Re-import your chats to refill it.")


# Every column the code below reads or writes.  A table that exists but is missing
# one of these is worse than a missing table, because it fails on the first INSERT.
_REQUIRED_COLUMNS = {
    "clients": ("name", "phone", "summary"),
    "messages": ("local_id", "timestamp", "sender", "type", "content",
                 "transcript", "source"),
    "items": ("client_id", "type", "description", "owner", "amount_mad",
              "due_date", "status", "source_message_id", "confidence"),
}


def _has_schema(conn):
    for table, columns in _REQUIRED_COLUMNS.items():
        present = _columns(conn, table)
        if not present or not set(columns) <= present:
            return False
    return True


def _ensure_schema(conn):
    """Create the schema if it is missing, rebuilding an older one.

    Called on every connection, not just at import: on Streamlit Community Cloud the
    filesystem is wiped on redeploy, so a long-running app can find its .db gone and
    would otherwise fail with "no such table" on the next query.
    """
    if _has_schema(conn):
        return
    _create_schema(conn)


def _create_schema(conn):
    _rebuild_schema(conn)
    conn.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                local_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                sender TEXT NOT NULL CHECK (sender IN ('me', 'client')),
                type TEXT NOT NULL CHECK (type IN ('text', 'voice')),
                content TEXT,
                transcript TEXT,
                audio_file TEXT,
                source TEXT NOT NULL DEFAULT 'export'
                    CHECK (source IN ('export', 'whatsapp')),
                UNIQUE(client_id, local_id),
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                type TEXT NOT NULL
                    CHECK (type IN ('task','promise','payment','deadline','question')),
                description TEXT NOT NULL,
                owner TEXT NOT NULL CHECK (owner IN ('me', 'client')),
                amount_mad REAL,
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
                source_message_id INTEGER NOT NULL,
                confidence TEXT NOT NULL CHECK (confidence IN ('high', 'low')),
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );
            CREATE INDEX IF NOT EXISTS idx_items_client
                ON items(client_id, status);
            CREATE INDEX IF NOT EXISTS idx_items_source
                ON items(client_id, source_message_id);
        """)


def init_db():
    """Explicitly create the schema.

    Not needed by callers any more: every connection checks for the schema and
    rebuilds it if absent.  Kept so a dev can force a fresh start with
    `python -c "from core import db; db.init_db()"`.
    """
    with _conn() as conn:
        _create_schema(conn)


# --------------------------------------------------------------------------- clients

def get_clients():
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM clients ORDER BY name COLLATE NOCASE")]


def get_client(client_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return dict(row) if row else None


def get_or_create_client(name, phone=None, summary=None):
    """Idempotent on name.  This is the live path's entry point (server/commands.py).

    The phone is masked before it is written: the dashboard never needs the real
    number to show a client, and a committed .db leaking a customer's number is
    the kind of thing that ends a submission badly.
    """
    name = (name or "").strip() or "Unknown Client"
    phone = mask_phone(phone) if phone else None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM clients WHERE name = ?", (name,)).fetchone()
        if row:
            if phone and phone != row["phone"]:
                conn.execute("UPDATE clients SET phone = ? WHERE id = ?",
                             (phone, row["id"]))
            if summary and summary != row["summary"]:
                conn.execute("UPDATE clients SET summary = ? WHERE id = ?",
                             (summary, row["id"]))
            return row["id"]
        cur = conn.execute("INSERT INTO clients (name, phone, summary) VALUES (?,?,?)",
                           (name, phone, summary))
        return cur.lastrowid


def set_client_summary(client_id, summary):
    with _conn() as conn:
        conn.execute("UPDATE clients SET summary = ? WHERE id = ?",
                     (summary, client_id))


def save_client(name, summary=None, phone=None):
    return get_or_create_client(name, phone=phone, summary=summary)


# -------------------------------------------------------------------------- messages

def next_local_id(client_id):
    with _conn() as conn:
        row = conn.execute("SELECT MAX(local_id) AS m FROM messages WHERE client_id = ?",
                           (client_id,)).fetchone()
    return (row["m"] or 0) + 1


def _message_key(row):
    """Identity of a message for re-import matching.

    Deliberately excludes the transcript: a second import of the same chat would
    otherwise fail to match a voice note whose transcript has since been filled in.
    """
    return (row["timestamp"], row["sender"], row["type"], (row["content"] or "").strip())


def existing_message_keys(client_id):
    """{message identity -> local_id} already stored for this client."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT local_id, timestamp, sender, type, content FROM messages "
            "WHERE client_id = ?", (client_id,)).fetchall()
    return {_message_key(r): r["local_id"] for r in rows}


def save_messages(client_id, messages):
    """Insert messages, skipping any (client_id, local_id) already stored.

    Returns (inserted, skipped).
    """
    inserted = skipped = 0
    with _conn() as conn:
        for m in messages:
            local_id = m.get("local_id") or m.get("id")
            if not local_id:
                continue
            try:
                conn.execute("""
                    INSERT INTO messages
                        (client_id, local_id, timestamp, sender, type, content,
                         transcript, audio_file, source)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    client_id,
                    local_id,
                    m["timestamp"],
                    _norm_sender(m.get("sender")),
                    m.get("type", "text"),
                    m.get("content"),
                    m.get("transcript"),
                    m.get("audio_file") or (
                        m.get("content") if m.get("type") == "voice" else None),
                    m.get("source", "export"),
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1  # re-import of an already stored message
    return inserted, skipped


def get_messages(client_id, limit=None):
    with _conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM messages WHERE client_id = ? "
            "ORDER BY timestamp ASC, local_id ASC", (client_id,))]
    return rows[-limit:] if limit and limit > 0 else rows


def get_message(ref, client_id=None):
    """Fetch one message from an Item.source_message_id.

    source_message_id is a *local_id*, not the row primary key, so local_id is
    tried first when a client_id is supplied.  The single-argument form (what
    ui.components.item_card uses) prefers local_id for the same reason, because
    matching a small local_id against the global id column silently returns
    another client's row.
    """
    with _conn() as conn:
        if client_id is not None:
            row = conn.execute(
                "SELECT * FROM messages WHERE client_id = ? AND local_id = ?",
                (client_id, ref)).fetchone()
            if row:
                return dict(row)
        else:
            row = conn.execute(
                "SELECT * FROM messages WHERE local_id = ? ORDER BY client_id LIMIT 1",
                (ref,)).fetchone()
            if row:
                return dict(row)
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (ref,)).fetchone()
        return dict(row) if row else None


def get_source_message(local_id, client_id=None):
    """Same lookup as get_message, kept because the UI layers call this name."""
    return get_message(local_id, client_id)


def set_transcript(message_row_id, text):
    with _conn() as conn:
        conn.execute("UPDATE messages SET transcript = ? WHERE id = ?",
                     (text, message_row_id))


# ---------------------------------------------------------------------------- items

def save_items(client_id, items):
    """Insert items, skipping ones already stored for this client."""
    with _conn() as conn:
        existing = {
            (r["type"], r["source_message_id"], (r["description"] or "").strip())
            for r in conn.execute(
                "SELECT type, source_message_id, description FROM items "
                "WHERE client_id = ?", (client_id,))
        }
        count = 0
        for i in items:
            key = (i["type"], i["source_message_id"], (i["description"] or "").strip())
            if key in existing:
                continue
            conn.execute("""
                INSERT INTO items
                    (client_id, type, description, owner, amount_mad, due_date,
                     source_message_id, confidence, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                client_id,
                i["type"],
                i["description"],
                _norm_sender(i.get("owner")),
                i.get("amount_mad"),
                i.get("due_date"),
                i["source_message_id"],
                i.get("confidence", "high"),
                i.get("status", "open"),
            ))
            existing.add(key)
            count += 1
    return count


def get_items(client_id=None, status="open"):
    """Open items across clients by default, with the client name attached."""
    query = ("SELECT items.*, clients.name AS client_name "
             "FROM items JOIN clients ON clients.id = items.client_id WHERE 1=1")
    params = []
    if client_id is not None:
        query += " AND items.client_id = ?"
        params.append(client_id)
    if status:
        query += " AND items.status = ?"
        params.append(status)
    query += " ORDER BY items.due_date IS NULL, items.due_date, clients.name"
    with _conn() as conn:
        return [dict(r) for r in conn.execute(query, params)]


def set_item_status(item_id, status):
    with _conn() as conn:
        conn.execute("UPDATE items SET status = ? WHERE id = ?", (status, item_id))


def get_money_owed():
    """[{client, amount_mad}] for open payments the client owes us."""
    with _conn() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT clients.name AS client, SUM(items.amount_mad) AS amount_mad
            FROM items JOIN clients ON clients.id = items.client_id
            WHERE items.type = 'payment' AND items.owner = 'client'
              AND items.status = 'open' AND items.amount_mad IS NOT NULL
            GROUP BY clients.id, clients.name
            ORDER BY amount_mad DESC
        """)]


def delete_open_items(client_id):
    """Re-import replaces the open items; done ones are the owner's own history."""
    with _conn() as conn:
        conn.execute("DELETE FROM items WHERE client_id = ? AND status = 'open'",
                     (client_id,))


def local_id_map(client_id):
    """{local_id: row_id} and {row_id: local_id} for resolving source_message_id."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, local_id FROM messages WHERE client_id = ?", (client_id,)).fetchall()
    return ({r["local_id"]: r["id"] for r in rows},
            {r["id"]: r["local_id"] for r in rows})
