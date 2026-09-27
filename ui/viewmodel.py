"""Pure view-model helpers: contract data -> display values.  Owner: D4.

No Streamlit import here, so everything is unit-tested in tests/ui/test_viewmodel.py.
"""
import os
import re
from datetime import date
from urllib.parse import quote

GOALS = {
    "payment_reminder": "Payment reminder",
    "confirm_delivery": "Confirm delivery",
    "quote_followup": "Quote follow-up",
    "thank_you": "Thank you",
}
BUCKETS = ("all", "overdue", "today", "upcoming")
BUCKET_LABELS = {"all": "All", "overdue": "Overdue", "today": "Due today", "upcoming": "Upcoming"}
ORDER_TYPES = ("task", "promise", "deadline")
URGENCY = ("urgent", "high", "normal", "low")
URGENCY_LABELS = {"all": "All", "urgent": "Urgent", "high": "High", "normal": "Normal", "low": "Low"}
_MASK_CHARS = set("*xX")


def parse_date(value):
    """'YYYY-MM-DD' (or ISO datetime) -> date; anything else -> None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def today():
    """WAKIL_TODAY=YYYY-MM-DD pins 'today' for tests and demos; otherwise the real date."""
    return parse_date(os.getenv("WAKIL_TODAY")) or date.today()


def classify_due(due_date, today):
    d = parse_date(due_date)
    if d is None:
        return "none"
    if d < today:
        return "overdue"
    if d == today:
        return "today"
    return "upcoming"


def due_label(due_date, today):
    d = parse_date(due_date)
    if d is None:
        return "No due date"
    days = (d - today).days
    if days < 0:
        return f"{-days} day{'' if days == -1 else 's'} late"
    if days == 0:
        return "Due today"
    if days == 1:
        return "Due tomorrow"
    return f"Due in {days} days"


def urgency(due_date, today):
    """Order urgency from the due date only: urgent / high / normal / low."""
    d = parse_date(due_date)
    if d is None:
        return "low"
    days = (d - today).days
    if days < 0:
        return "urgent"
    if days <= 1:
        return "high"
    if days <= 7:
        return "normal"
    return "low"


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fmt_mad(amount):
    try:
        return f"{float(amount):,.0f} MAD"
    except (TypeError, ValueError):
        return "-"


def initials(name):
    parts = str(name or "").split()
    if not parts:
        return "?"
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()


def _due_key(item):
    d = parse_date(item.get("due_date"))
    return (d is None, d or date.max, item.get("id") or 0)


def sort_by_due(items):
    """Earliest due date first; items without a date last; ties by id."""
    return sorted(items, key=_due_key)


def _bucket(item, today):
    b = classify_due(item.get("due_date"), today)
    return "upcoming" if b == "none" else b


def bucket_counts(items, today):
    counts = {b: 0 for b in BUCKETS}
    counts["all"] = len(items)
    for i in items:
        counts[_bucket(i, today)] += 1
    return counts


def filter_items(items, bucket, today):
    if bucket == "all":
        return sort_by_due(items)
    return sort_by_due([i for i in items if _bucket(i, today) == bucket])


def client_owes(items, client_id):
    """Open payments the client still owes the owner."""
    return sum(_num(i.get("amount_mad")) for i in items
               if i.get("client_id") == client_id and i.get("type") == "payment"
               and i.get("owner") == "client" and i.get("status", "open") == "open")


def orders(items, clients, today):
    """Orders = open task/promise/deadline items the owner ('me') must deliver."""
    names = {c.get("id"): c.get("name") for c in clients}
    rank = {u: n for n, u in enumerate(URGENCY)}
    rows = []
    for i in items:
        if i.get("owner") != "me" or i.get("type") not in ORDER_TYPES or i.get("status", "open") != "open":
            continue
        cid = i.get("client_id")
        rows.append({
            "item": i, "client_id": cid, "client": names.get(cid) or "Unknown client",
            "urgency": urgency(i.get("due_date"), today), "due_label": due_label(i.get("due_date"), today),
            "client_owes": client_owes(items, cid),
        })
    return sorted(rows, key=lambda r: (rank[r["urgency"]],) + _due_key(r["item"]))


def urgency_counts(rows):
    counts = {"all": len(rows), **{u: 0 for u in URGENCY}}
    for r in rows:
        counts[r["urgency"]] += 1
    return counts


def dashboard_metrics(items, owed, clients, today):
    """items: open Items (all clients). owed: db.get_money_owed()."""
    counts = bucket_counts(items, today)
    order_rows = orders(items, clients, today)
    promises = [i for i in items if i.get("type") == "promise"]
    return {
        "owed_total": sum(_num(o.get("amount_mad")) for o in owed),
        "owed_clients": sum(1 for o in owed if _num(o.get("amount_mad")) > 0),
        "owed_overdue": sum(_num(i.get("amount_mad")) for i in items
                            if i.get("type") == "payment" and i.get("owner") == "client"
                            and classify_due(i.get("due_date"), today) == "overdue"),
        "open": counts["all"],
        "overdue": counts["overdue"],
        "today": counts["today"],
        "orders": len(order_rows),
        "orders_urgent": sum(1 for r in order_rows if r["urgency"] == "urgent"),
        "promises": len(promises),
        "promises_mine": sum(1 for p in promises if p.get("owner") == "me"),
        "promises_client": sum(1 for p in promises if p.get("owner") == "client"),
        "to_verify": sum(1 for i in items if i.get("confidence") == "low"),
    }


def owed_rows(owed, items, clients, today):
    """One row per client who owes money: overdue first, then biggest amount."""
    ids = {c.get("name"): c.get("id") for c in clients}
    rows = []
    for o in owed:
        amount = _num(o.get("amount_mad"))
        if amount <= 0:
            continue
        name = o.get("client") or "Unknown client"
        cid = ids.get(name)
        pays = sort_by_due([i for i in items if cid is not None and i.get("client_id") == cid
                            and i.get("type") == "payment" and i.get("owner") == "client"])
        first = pays[0] if pays else None
        due = first.get("due_date") if first else None
        rows.append({
            "client": name, "client_id": cid, "amount_mad": amount, "due_date": due,
            "overdue": classify_due(due, today) == "overdue", "due_label": due_label(due, today),
            "initials": initials(name), "item": first, "description": (first or {}).get("description", ""),
        })
    return sorted(rows, key=lambda r: (not r["overdue"], -r["amount_mad"]))


def parse_brief(text):
    """'Label: body' lines -> [(label, body)]; lines without a short label -> ('', line)."""
    out = []
    for line in str(text or "").splitlines():
        line = re.sub(r"^\s*(\d+[.)]|[-*])\s", "", line)
        line = re.sub(r"[*_`#]", "", line)  # LLMs often bold the labels: **Status:**
        line = re.sub(r"^\s*line\s*\d+\s*[-:.]\s*", "", line, flags=re.I).strip()
        if not line:
            continue
        label, sep, body = line.partition(":")
        if sep and 0 < len(label.strip()) <= 30:
            out.append((label.strip(), body.strip()))
        else:
            out.append(("", line))
    return out


def dialable(phone):
    """Digits of a real phone number, or '' when it is masked ('[PHONE]', '6** **') or too short."""
    raw = str(phone or "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    return "" if _MASK_CHARS & set(raw) or len(digits) < 8 else digits


def whatsapp_link(text, phone=None):
    """wa.me link that only PRE-FILLS the message; the owner still presses send."""
    return f"https://wa.me/{dialable(phone)}?text={quote(str(text or ''), safe='')}"


def _items(n):
    return f"{n} item{'' if n == 1 else 's'}"


def headline(metrics):
    """One plain sentence for the hero: what is late and what is due today."""
    late, due = metrics.get("overdue", 0), metrics.get("today", 0)
    if late and due:
        return f"{_items(late)} late and {due} due today."
    if late:
        return f"{_items(late)} late."
    if due:
        return f"{_items(due)} due today."
    return "Nothing is late or due today."


def long_date(today):
    """'Sunday 27 September' (no zero padding, English names)."""
    return f"{today:%A} {today.day} {today:%B}"
