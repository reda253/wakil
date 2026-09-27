"""Storage.  Owner: D3.

SQLite (wakil.db / WAKIL_DB) locally; Postgres when DATABASE_URL is a postgres URL.
Tables: clients(id, name, phone), messages, items, matching core/contracts.py.

Which backend is in use is decided once, here, from the environment:
  WAKIL_DB set            -> SQLite at that path (tests and local demos)
  DATABASE_URL postgres   -> Postgres, which is what Streamlit Cloud and the webhook
                             server share so both see the same rows
  neither                 -> SQLite at ./wakil.db
Every function below goes through _conn() and the SQL is written to run unchanged on
both engines, so this file never has to branch on backend outside connect().

Two id spaces, and confusing them is the classic bug here:
  * messages.id        the row primary key, global and ever-growing
  * messages.local_id  the per-chat sequential id the parser assigned, and the value
                        every Item.source_message_id points at ("view source")
Every read helper that a source_message_id can reach accepts either, so callers on
either side of the contract still get the right row.
"""
import contextlib
import os
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit, urlunsplit

from dotenv import load_dotenv

from core.parser import mask_phone

# The backend is decided from the environment at import time, so .env has to be in
# os.environ *before* the reads below.  app.py loads it too; loading here as well means
# a script, a test or the webhook server can never silently land on the wrong database
# just because it imported core.db first.  Existing env vars always win.
load_dotenv()

DB_PATH = os.getenv("WAKIL_DB") or "wakil.db"
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
_PG = not os.getenv("WAKIL_DB") and DATABASE_URL.startswith(
    ("postgres://", "postgresql://"))

_SENDER_ALIASES = {"owner": "me", "me": "me", "client": "client"}
_SENDERS = ("me", "client")
_VALID_TYPES = ("text", "voice")

# The only schema this module is ever allowed to DROP a populated one out of.  See
# _drop_refusal for why that needs saying out loud.
_TEST_SCHEMA = "wakil_test"
# Opt-in that lets that rule be overridden on purpose.  See _drop_refusal.
_ALLOW_DROP_ENV = "WAKIL_ALLOW_DROP"

_pool = None
_pg_schema_ok = False


def backend():
    return "postgres" if _PG else "sqlite"


def describe():
    """Where the data lives, safe to log: the password is masked."""
    if not _PG:
        return f"sqlite:{DB_PATH}"
    parts = urlsplit(DATABASE_URL)
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    netloc = f"{parts.username}:***@{host}" if parts.username else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _pg_search_path():
    """The schema a Postgres URL selects, from options=-csearch_path=NAME."""
    options = parse_qs(urlsplit(DATABASE_URL).query).get("options", [""])[0]
    match = re.search(r"search_path\s*=\s*([^\s,]+)", options)
    return match.group(1).strip("\"'") if match else "public"


def _allow_drop():
    """Has someone deliberately asked to wipe a populated schema?  Never default."""
    return (os.getenv(_ALLOW_DROP_ENV) or "").strip().lower() in ("1", "true", "yes", "on")


def _drop_refusal(schema, had_tables):
    """Why dropping every table here would be wrong, or None if it is fine.

    _rebuild_schema() runs DROP TABLE against whatever schema the connection is
    pointed at.  That is exactly right for a scratch SQLite file and for the
    throwaway *_test schema the test suite wipes on every test - and catastrophic
    for anything else, because a TEST_DATABASE_URL that lost its search_path
    option would otherwise quietly empty the shared database.  So: a populated
    schema other than the test one is refused, loudly.

    The one exception is _ALLOW_DROP_ENV, which is how a person says out loud
    "yes, empty this one on purpose" - seeding the demo database from scratch, or
    rehearsing that seed.  It has to be an env var rather than an init_db() argument
    because the test fixtures call init_db() too: that is precisely the
    misconfigured-TEST_DATABASE_URL disaster the guard exists to stop, so the
    opt-in cannot be something the destructive path grants itself.
    """
    if not had_tables:
        return None                      # nothing to lose: bootstrapping a new one
    if schema == _TEST_SCHEMA:
        return None
    if _allow_drop():
        print(f"[db] {_ALLOW_DROP_ENV} is set: dropping every table in {schema!r} "
              "on purpose, as asked.")
        return None
    return (f"schema {schema!r} already has tables and is not {_TEST_SCHEMA!r}; "
            f"refusing to drop them. Set {_ALLOW_DROP_ENV}=1 if you mean it")


def _norm_sender(value):
    """Accept both vocabularies ('owner' from contracts.py, 'me' from the old code)."""
    return _SENDER_ALIASES.get((value or "").strip().lower(), "client")


def _pg_pool():
    global _pool
    if _pool is None:
        from psycopg2.pool import ThreadedConnectionPool  # Streamlit serves each session on its own thread
        _pool = ThreadedConnectionPool(1, 8, DATABASE_URL, connect_timeout=10)
        print(f"[db] backend=postgres {describe()}")
    return _pool


def close_pool():
    global _pool, _pg_schema_ok
    if _pool is not None:
        _pool.closeall()
    _pool, _pg_schema_ok = None, False


class _PgCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone() if self._cur.description else None

    def fetchall(self):
        return self._cur.fetchall() if self._cur.description else []

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def rowcount(self):
        return self._cur.rowcount


class _PgConn:
    """sqlite3-shaped facade over a pooled psycopg2 connection."""

    def __init__(self):
        import psycopg2
        pool = _pg_pool()
        raw = pool.getconn()
        try:
            with raw.cursor() as cur:
                cur.execute("SELECT 1")
        except psycopg2.Error:  # the server closed this idle pooled connection
            pool.putconn(raw, close=True)
            raw = pool.getconn()
        self.raw = raw

    def execute(self, sql, params=()):
        from psycopg2.extras import RealDictCursor
        if "%" in sql:
            raise ValueError(f"% is reserved by psycopg2, use ? placeholders: {sql}")
        cur = self.raw.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql.replace("?", "%s"), tuple(params))
        return _PgCursor(cur)

    def executescript(self, script):
        with self.raw.cursor() as cur:
            cur.execute(script)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        _pg_pool().putconn(self.raw)


def connect():
    if _PG:
        return _PgConn()
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
    if _PG:
        return {r["column_name"] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?", (table,))}
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _rebuild_schema(conn):
    """Drop all three tables, but only report it if anything was actually there.

    Only ever called when _has_schema() has already decided the schema is unusable,
    and the reason is usually a CHECK constraint: SQLite cannot ALTER one, so the
    previous messages.sender = ('owner','client') table would reject every insert of
    'me' no matter what CREATE TABLE IF NOT EXISTS does.  These files are local
    scratch (gitignored) and the chat export is the real source of truth, so
    rebuilding is both the only option and the correct one.

    A brand new empty file lands here too, and must stay silent: telling a first
    time user their database "had an older schema" is both false and alarming.
    """
    had_tables = any(_columns(conn, table) for table in _REQUIRED_COLUMNS)
    # Postgres only.  A local SQLite file is scratch by definition, so wiping it is
    # the point; on a shared server the same DROP pointed at the wrong schema is the
    # disaster this refuses.
    refusal = _drop_refusal(_pg_search_path(), had_tables) if _PG else None
    if refusal:
        raise RuntimeError(
            f"[db] cannot rebuild the schema: {refusal}. Set WAKIL_DB to use a local "
            "SQLite file, or point DATABASE_URL at a dedicated throwaway schema.")
    conn.executescript(
        "DROP TABLE IF EXISTS items;"
        "DROP TABLE IF EXISTS messages;"
        "DROP TABLE IF EXISTS clients;")
    if had_tables:
        print(f"[db] '{describe()}' had an older schema and was rebuilt. "
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
    would otherwise fail with "no such table" on the next query.  On Postgres the
    check runs once per process, because the database is shared and does not vanish
    between requests - and re-checking a shared schema on every query would mean
    every one of them racing to rebuild it.
    """
    global _pg_schema_ok
    if _PG and _pg_schema_ok:
        return
    if not _has_schema(conn):
        _create_schema(conn)
    _pg_schema_ok = _PG


# The DDL, verbatim, for both engines.  _create_schema() translates the two
# SQLite-only spellings below into their Postgres equivalents; everything else in
# here is already valid on both.
_SCHEMA_SQL = """
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
        """


def _create_schema(conn):
    _rebuild_schema(conn)
    ddl = _SCHEMA_SQL
    if _PG:
        ddl = (ddl.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                  .replace("amount_mad REAL", "amount_mad DOUBLE PRECISION"))
    conn.executescript(ddl)


def init_db():
    """Explicitly create the schema, dropping whatever was there.

    Not needed by callers any more: every connection checks for the schema and
    rebuilds it if absent.  Kept so a dev can force a fresh start with
    `python -c "from core import db; db.init_db()"`.
    """
    global _pg_schema_ok
    # connect() rather than _conn(): _conn() would ensure the schema first, and this
    # rebuild would then trip its own drop guard on the tables _conn() had just
    # created - so a first run against an empty Postgres schema used to fail on the
    # second pass.  One create, not two.
    conn = connect()
    try:
        _create_schema(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _pg_schema_ok = _PG


# --------------------------------------------------------------------------- clients

def get_clients():
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM clients ORDER BY LOWER(name), name")]


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
        # RETURNING rather than lastrowid: psycopg2 has no lastrowid, and SQLite has
        # supported RETURNING since 3.35, so this stays one code path for both.
        return conn.execute(
            "INSERT INTO clients (name, phone, summary) VALUES (?,?,?) RETURNING id",
            (name, phone, summary)).fetchone()["id"]


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


def _is_duplicate(exc):
    """True if this failure was a UNIQUE violation, on either engine.

    sqlite3 says "UNIQUE constraint failed: messages.client_id, messages.local_id";
    psycopg2 raises UniqueViolation, sqlstate 23505.  Either way ON CONFLICT should
    have absorbed the duplicate already, so reaching this is the unexpected case.
    """
    if getattr(exc, "pgcode", None) == "23505":
        return True
    text = str(exc).lower()
    return ("unique" in text and "constraint" in text) or "duplicate key" in text


def save_messages(client_id, messages, problems=None):
    """Insert messages, skipping any (client_id, local_id) already stored.

    Returns (inserted, skipped).  `problems`, if a list is passed, collects
    human-readable notes about messages that were not stored.

    A re-import trips UNIQUE(client_id, local_id) and is skipped silently, which is
    the boring case worth handling quietly.  Any *other* IntegrityError is a genuine
    defect, and it used to be counted as a duplicate too: a malformed message then
    disappeared from the conversation with nothing logged anywhere, so the dashboard
    simply showed an incomplete chat and the owner had no way to tell.

    Two things about that, both of which only bite on Postgres:

      * ON CONFLICT DO NOTHING, not catch-and-count.  Postgres aborts the whole
        transaction on a failed INSERT, so catching the duplicate and carrying on
        would fail every statement after it.
      * a SAVEPOINT per message, so that when a genuinely bad message does abort the
        transaction it takes down one row rather than the rest of the batch.  SQLite
        supports savepoints too, so this stays one code path.
    """
    inserted = skipped = 0

    def note(text):
        if problems is None:
            raise ValueError(text)   # nobody is watching: fail loudly, do not lie
        problems.append(text)

    with _conn() as conn:
        for m in messages:
            local_id = m.get("local_id") or m.get("id")
            preview = (m.get("content") or "")[:40]
            if not local_id:
                note(f"A message with no id was dropped: {preview!r}")
                continue

            msg_type = m.get("type") or "text"
            if msg_type not in _VALID_TYPES:
                note(f"Message {local_id} had type {m.get('type')!r}, stored as text: "
                     f"{preview!r}")
                msg_type = "text"

            conn.execute("SAVEPOINT one_message")
            try:
                cur = conn.execute("""
                    INSERT INTO messages
                        (client_id, local_id, timestamp, sender, type, content,
                         transcript, audio_file, source)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT (client_id, local_id) DO NOTHING
                """, (
                    client_id,
                    local_id,
                    m["timestamp"],
                    _norm_sender(m.get("sender")),
                    msg_type,
                    m.get("content"),
                    m.get("transcript"),
                    m.get("audio_file") or (
                        m.get("content") if msg_type == "voice" else None),
                    m.get("source", "export"),
                ))
                conn.execute("RELEASE SAVEPOINT one_message")
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1  # re-import of an already stored message
            except Exception as exc:  # sqlite3.IntegrityError, or psycopg2.Error
                conn.execute("ROLLBACK TO SAVEPOINT one_message")
                conn.execute("RELEASE SAVEPOINT one_message")
                if _is_duplicate(exc):
                    skipped += 1  # some other UNIQUE constraint, not the expected one
                else:
                    note(f"Message {local_id} was rejected by the database "
                         f"({exc}): {preview!r}")
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
    """[{client, amount_mad}] for open money the client owes us.

    Counts promises as well as payments.  "Ana ghadi nsiftlik l'avance ghedda" is a
    promise carrying 7500 MAD, not a payment, and it is the single most common way
    money is owed in a trade - so counting only type='payment' reported 0 MAD owed
    for exactly the conversations this product exists to catch.  Both still require
    owner='client', status='open' and a real amount, so a settled or unpriced item
    cannot inflate the total.
    """
    with _conn() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT clients.name AS client, SUM(items.amount_mad) AS amount_mad
            FROM items JOIN clients ON clients.id = items.client_id
            WHERE items.type IN ('payment', 'promise') AND items.owner = 'client'
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
