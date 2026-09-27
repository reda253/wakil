"""core.db on both backends.  SQLite always; Postgres only when TEST_DATABASE_URL is set.

TEST_DATABASE_URL MUST select the wakil_test schema (options=-csearch_path=wakil_test):
init_db() drops every table in the schema the URL selects.
"""
import importlib
import os

import pytest

BACKENDS = ["sqlite"] + (["postgres"] if os.getenv("TEST_DATABASE_URL") else [])
NEEDS_PG = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),
                              reason="needs TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def _reload_after():
    """Autouse fixtures tear down last, i.e. after monkeypatch restored the env, so
    this reload leaves core.db configured as the rest of the suite expects."""
    yield
    from core import db as module
    module.close_pool()
    importlib.reload(module)


@pytest.fixture(params=BACKENDS)
def db(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        monkeypatch.setenv("WAKIL_DB", str(tmp_path / "test.db"))
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.delenv("WAKIL_DB", raising=False)
        monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    from core import db as module
    module = importlib.reload(module)
    module.init_db()
    yield module
    module.close_pool()


def _msg(local_id, text, sender="client"):
    return {"local_id": local_id, "timestamp": f"2026-09-2{local_id} 10:00",
            "sender": sender, "type": "text", "content": text}


def test_backend_matches_fixture(db, request):
    assert db.backend() == request.node.callspec.params["db"]


def test_clients_idempotent_and_sorted_case_insensitive(db):
    karim = db.get_or_create_client("Karim", "+212 612 345 678")
    assert db.get_or_create_client("Karim") == karim
    db.get_or_create_client("amine")
    assert [c["name"] for c in db.get_clients()] == ["amine", "Karim"]
    assert db.get_client(karim)["phone"] != "+212 612 345 678"  # masked


def test_save_messages_skips_duplicates(db):
    cid = db.get_or_create_client("Karim")
    batch = [_msg(1, "hello"), _msg(2, "send the invoice", "me")]
    assert db.save_messages(cid, batch) == (2, 0)
    assert db.save_messages(cid, batch) == (0, 2)
    # the connection is still usable after the skipped inserts (Postgres aborts
    # the transaction on a caught IntegrityError; ON CONFLICT must prevent that)
    assert [m["local_id"] for m in db.get_messages(cid)] == [1, 2]


def test_items_money_owed_and_status(db):
    cid = db.get_or_create_client("Karim")
    db.save_messages(cid, [_msg(1, "I will pay 1500 on Friday")])
    n = db.save_items(cid, [{
        "type": "payment", "description": "Pay 1500 MAD", "owner": "client",
        "amount_mad": 1500, "due_date": "2026-09-25", "source_message_id": 1,
        "confidence": "high"}])
    assert n == 1
    items = db.get_items()
    assert items[0]["client_name"] == "Karim"
    owed = db.get_money_owed()
    assert owed == [{"client": "Karim", "amount_mad": 1500.0}]
    assert isinstance(owed[0]["amount_mad"], float)
    db.set_item_status(items[0]["id"], "done")
    assert db.get_items() == []


def test_a_promised_payment_counts_as_money_owed(db):
    """A promise to pay is the commonest way money is owed, so it must count.

    Real extraction turns "ghadi nsiftlik l'avance ghedda" into type='promise' with an
    amount, not type='payment'.  Counting payments alone reported 0 MAD owed for the
    exact conversation this product exists to catch.
    """
    cid = db.get_or_create_client("Ahmed")
    db.save_messages(cid, [_msg(1, "ok, ghadi nsiftlik l'avance ghedda")])
    db.save_items(cid, [{
        "type": "promise", "description": "Send the 50% advance tomorrow",
        "owner": "client", "amount_mad": 7500, "due_date": "2026-09-28",
        "source_message_id": 1, "confidence": "high"}])
    assert db.get_money_owed() == [{"client": "Ahmed", "amount_mad": 7500.0}]


def test_money_owed_ignores_my_own_promises_and_unpriced_items(db):
    cid = db.get_or_create_client("Ahmed")
    db.save_messages(cid, [_msg(1, "..."), _msg(2, "..."), _msg(3, "...")])
    db.save_items(cid, [
        {"type": "promise", "description": "I will deliver Thursday", "owner": "me",
         "amount_mad": 15000, "due_date": "2026-10-12", "source_message_id": 1,
         "confidence": "high"},
        {"type": "task", "description": "Send the invoice", "owner": "me",
         "amount_mad": None, "due_date": None, "source_message_id": 2,
         "confidence": "high"},
        {"type": "question", "description": "How many drawers?", "owner": "client",
         "amount_mad": None, "due_date": None, "source_message_id": 3,
         "confidence": "high"},
    ])
    assert db.get_money_owed() == []


def test_get_message_scoped_by_client(db):
    a = db.get_or_create_client("A")
    b = db.get_or_create_client("B")
    db.save_messages(a, [_msg(1, "from A")])
    db.save_messages(b, [_msg(1, "from B")])
    assert db.get_message(1, client_id=b)["content"] == "from B"


def test_backend_selection(monkeypatch):
    from core import db as module
    monkeypatch.delenv("WAKIL_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    assert importlib.reload(module).backend() == "postgres"
    monkeypatch.setenv("DATABASE_URL", "postgress://typo")
    assert importlib.reload(module).backend() == "sqlite"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("WAKIL_DB", "local.db")
    assert importlib.reload(module).backend() == "sqlite"


def test_describe_masks_password(monkeypatch):
    from core import db as module
    monkeypatch.delenv("WAKIL_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://wakil:s3cret@db.example:5432/wakil?sslmode=require")
    text = importlib.reload(module).describe()
    assert "s3cret" not in text and "db.example" in text and text.startswith("postgres")


@NEEDS_PG
def test_pool_recovers_from_closed_connection(monkeypatch):
    from core import db as module
    monkeypatch.delenv("WAKIL_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    module = importlib.reload(module)
    module.init_db()
    pool = module._pg_pool()
    raw = pool.getconn()
    raw.close()                      # what Guepard does to an idle connection
    pool.putconn(raw)
    assert module.get_clients() == []


# ---------------------------------------------------------------------------
# D3 additions.  The suite above came with Task 2; these cover the two things it
# does not: that one bad message cannot take the rest of the batch with it, and
# that a misconfigured database URL cannot drop somebody else's tables.
#
# Both matter on Postgres specifically.  A caught IntegrityError there leaves the
# transaction aborted, so every later statement in the batch would fail with
# "current transaction is aborted" - which is the silent data loss this guard
# exists to prevent, just wearing a different hat.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_allow_drop(monkeypatch):
    """Nobody's real .env may make these tests destructive by accident."""
    monkeypatch.delenv("WAKIL_ALLOW_DROP", raising=False)


def test_search_path_is_read_out_of_the_url(monkeypatch):
    from core import db as module
    monkeypatch.delenv("WAKIL_DB", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@h:5432/d?sslmode=require&options=-csearch_path%3Dwakil_test")
    assert importlib.reload(module)._pg_search_path() == "wakil_test"


def test_search_path_defaults_to_public_when_the_url_says_nothing(monkeypatch):
    from core import db as module
    monkeypatch.delenv("WAKIL_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d?sslmode=require")
    assert importlib.reload(module)._pg_search_path() == "public"


def test_dropping_the_test_schema_is_allowed():
    from core import db
    assert db._drop_refusal("wakil_test", had_tables=True) is None


def test_dropping_a_populated_foreign_schema_is_refused():
    from core import db
    refusal = db._drop_refusal("public", had_tables=True)
    assert refusal and "public" in refusal and "wakil_test" in refusal


def test_bootstrapping_an_empty_schema_is_never_refused():
    """A brand new database has nothing to lose, so it may always be created."""
    from core import db
    assert db._drop_refusal("public", had_tables=False) is None
    assert db._drop_refusal("", had_tables=False) is None


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_the_allow_drop_opt_in_permits_a_populated_foreign_schema(monkeypatch, value):
    from core import db
    monkeypatch.setenv("WAKIL_ALLOW_DROP", value)
    assert db._drop_refusal("public", had_tables=True) is None


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_allow_drop_reads_only_an_explicit_yes(monkeypatch, value):
    """Anything that is not clearly a yes must leave the guard shut."""
    from core import db
    monkeypatch.setenv("WAKIL_ALLOW_DROP", value)
    assert db._drop_refusal("public", had_tables=True) is not None


def test_allow_drop_is_off_unless_it_was_actually_set():
    from core import db
    assert db._allow_drop() is False
    assert db._drop_refusal("public", had_tables=True) is not None


def test_rebuild_really_drops_when_the_opt_in_is_set(monkeypatch):
    """The opt-in wired into _rebuild_schema, not only the helper beside it."""
    import sqlite3
    from core import db as module
    module = importlib.reload(module)
    monkeypatch.setenv("WAKIL_ALLOW_DROP", "1")
    monkeypatch.setattr(module, "_PG", True)
    monkeypatch.setattr(module, "_pg_search_path", lambda: "public")
    monkeypatch.setattr(module, "_columns", lambda conn, table: {"id", "name"})
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT)")
    module._rebuild_schema(conn)
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    conn.close()


def test_rebuild_actually_refuses_and_leaves_the_tables_alone(monkeypatch):
    """The guard wired into _rebuild_schema, not just the helper beside it.

    This is the case that would otherwise empty somebody's database, so it is worth
    asserting on the table surviving and not only on the exception.
    """
    import sqlite3
    from core import db as module
    module = importlib.reload(module)
    monkeypatch.setattr(module, "_PG", True)              # pretend we are on Postgres
    monkeypatch.setattr(module, "_pg_search_path", lambda: "public")
    monkeypatch.setattr(module, "_columns", lambda conn, table: {"id", "name"})
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT)")
    with pytest.raises(RuntimeError, match="public"):
        module._rebuild_schema(conn)
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("clients",)]
    conn.close()


def test_rebuild_is_allowed_for_the_test_schema(monkeypatch):
    import sqlite3
    from core import db as module
    module = importlib.reload(module)
    monkeypatch.setattr(module, "_PG", True)
    monkeypatch.setattr(module, "_pg_search_path", lambda: "wakil_test")
    monkeypatch.setattr(module, "_columns", lambda conn, table: {"id", "name"})
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT)")
    module._rebuild_schema(conn)                          # must not raise
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    conn.close()


def test_one_bad_message_does_not_lose_the_rest_of_the_batch(db):
    """A NOT NULL violation mid-batch must be reported, not fatal.

    This is the case the savepoint exists for: on Postgres the failed INSERT
    poisons the transaction, so without the rollback the two good messages that
    follow would be lost as well.
    """
    cid = db.get_or_create_client("Karim")
    problems = []
    inserted, skipped = db.save_messages(cid, [
        _msg(1, "good one"),
        {"local_id": 2, "timestamp": None, "sender": "client", "type": "text",
         "content": "no timestamp, violates NOT NULL"},
        _msg(3, "good two"),
    ], problems=problems)
    assert (inserted, skipped) == (2, 0)
    assert [m["local_id"] for m in db.get_messages(cid)] == [1, 3]
    assert len(problems) == 1 and "2" in problems[0]


def test_a_bad_type_is_coerced_and_reported(db):
    cid = db.get_or_create_client("Karim")
    problems = []
    db.save_messages(cid, [dict(_msg(1, "hi"), type="sticker")], problems=problems)
    assert db.get_messages(cid)[0]["type"] == "text"
    assert any("stored as text" in p for p in problems), problems


def test_a_message_with_no_id_is_reported(db):
    cid = db.get_or_create_client("Karim")
    problems = []
    db.save_messages(cid, [{"timestamp": "2026-09-21 10:00", "sender": "client",
                            "type": "text", "content": "orphan"}],
                     problems=problems)
    assert any("no id" in p for p in problems), problems
    assert db.get_messages(cid) == []


def test_saving_without_a_problems_list_fails_loudly(db):
    cid = db.get_or_create_client("Karim")
    with pytest.raises(ValueError):
        db.save_messages(cid, [{"timestamp": "2026-09-21 10:00", "sender": "client",
                                "type": "text", "content": "orphan"}])


def test_describe_reports_the_active_backend_without_leaking_the_password(db, request):
    described = db.describe()
    if request.node.callspec.params["db"] == "sqlite":
        assert described == f"sqlite:{db.DB_PATH}"
    else:
        assert described.startswith(("postgres://", "postgresql://"))
        assert "***" in described
        # the real password must never reach a log line
        _, _, secret = os.environ["TEST_DATABASE_URL"].split("://", 1)[1].partition("@")[0].partition(":")
        assert secret, "TEST_DATABASE_URL should carry a password to test against"
        assert secret not in described


def test_init_db_is_idempotent_on_both_backends(db):
    cid = db.get_or_create_client("Karim")
    db.save_messages(cid, [_msg(1, "kept")])
    db.init_db()                     # rebuilds, so the row goes but the schema stays
    assert db.get_clients() == []
    assert db.backend() in ("sqlite", "postgres")


def test_init_db_on_a_fresh_postgres_schema_does_not_trip_its_own_guard(db):
    """init_db() used to create the schema twice and fail on the second pass.

    _conn() ensures the schema, then init_db() asked for a rebuild, and that rebuild
    saw the tables _conn() had just made and refused - so a *first* run against an
    empty database failed while a re-run worked.  SQLite cannot catch this: it has no
    drop guard, so its double create is invisible.

    The fixture has already created the schema, so drop the tables to get back to the
    genuinely-empty state that used to fail.
    """
    if db.backend() != "postgres":
        pytest.skip("needs TEST_DATABASE_URL")
    conn = db.connect()             # empty again, as a brand new database would be
    try:
        conn.executescript("DROP TABLE IF EXISTS items;DROP TABLE IF EXISTS messages;"
                           "DROP TABLE IF EXISTS clients;")
        conn.commit()
    finally:
        conn.close()
    db.close_pool()

    db.init_db()                     # the thing that used to raise
    cid = db.get_or_create_client("Karim")
    assert db.save_messages(cid, [_msg(1, "hello")]) == (1, 0)
    assert db.get_messages(cid)
