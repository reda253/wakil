"""Pure HTML builders rendered with st.html.  Owner: D4.

Rule: every dynamic value goes through esc(). Colors carry state only:
danger = overdue/urgent, warn = needs check, everything else neutral.
"""
from html import escape

from ui.viewmodel import URGENCY_LABELS, classify_due, due_label, fmt_mad, initials

_OWNER_SENDERS = ("owner", "me")  # contracts.py says "owner"; core/db.py stores "me"


def esc(value):
    return escape("" if value is None else str(value), quote=True)


def badge(text, tone="neutral"):
    return f'<span class="w-badge w-{tone}">{esc(text)}</span>'


def metric_html(icon, label, value, unit=""):
    unit_html = f' <span class="w-unit">{esc(unit)}</span>' if unit else ""
    return (f'<div class="w-metric"><span class="w-ico" aria-hidden="true">{esc(icon)}</span>'
            f'<div class="w-metric-value">{esc(value)}{unit_html}</div>'
            f'<div class="w-caption">{esc(label)}</div></div>')


def kv_html(pairs):
    rows = "".join(f'<div class="w-kv"><span>{esc(a)}</span><b>{esc(b)}</b></div>' for a, b in pairs)
    return f'<div class="w-kv-list">{rows}</div>'


def owed_row_html(row):
    state = " w-overdue" if row["overdue"] else ""
    flag = badge("Overdue", "danger") if row["overdue"] else ""
    return (f'<div class="w-row{state}"><div class="w-row-left">'
            f'<span class="w-avatar">{esc(row["initials"])}</span>'
            f'<div><div class="w-row-title">{esc(row["client"])} {flag}</div>'
            f'<div class="w-caption">{esc(row["description"])}</div></div></div>'
            f'<div class="w-row-right"><div class="w-amount">{esc(fmt_mad(row["amount_mad"]))}</div>'
            f'<div class="w-caption">{esc(row["due_label"])}</div></div></div>')


def item_html(item, client_name, today, source=None, urgency=None):
    due = item.get("due_date")
    low = item.get("confidence") == "low"
    chips = []
    if urgency:
        chips.append(badge(URGENCY_LABELS[urgency], "danger" if urgency == "urgent" else "neutral"))
    chips.append(badge((item.get("type") or "item").capitalize()))
    chips.append(badge(due_label(due, today), "danger" if classify_due(due, today) == "overdue" else "neutral"))
    if item.get("amount_mad") not in (None, ""):
        chips.append(badge(fmt_mad(item["amount_mad"])))
    if low:
        chips.append(badge("Needs check", "warn"))
    if source == "whatsapp":
        chips.append(badge("via WhatsApp"))
    who = f'<span class="w-muted">{esc(client_name)}</span>' if client_name else ""
    classes = "w-item" + (" w-low" if low else "") + (" w-done" if item.get("status") == "done" else "")
    return (f'<div class="{classes}"><div class="w-chips">{"".join(chips)}{who}</div>'
            f'<div class="w-item-desc">{esc(item.get("description", ""))}</div></div>')


def brief_html(pairs):
    lis = "".join(
        f'<li><span class="w-num">{n + 1}</span><div>'
        + (f"<b>{esc(label)}:</b> " if label else "")
        + f"{esc(body)}</div></li>"
        for n, (label, body) in enumerate(pairs))
    return f'<div class="w-brief"><div class="w-eyebrow">Pre-call summary</div><ol>{lis}</ol></div>'


def message_html(message):
    mine = message.get("sender") in _OWNER_SENDERS
    voice = message.get("type") == "voice"
    body = message.get("transcript") if voice else message.get("content")
    if voice and not body:
        body = "(voice note, not transcribed yet)"
    tags = badge("Voice note") if voice else ""
    if message.get("source") == "whatsapp":
        tags += badge("via WhatsApp")
    who = "You" if mine else "Client"
    ref = message.get("local_id", message.get("id"))
    return (f'<div class="w-msg {"w-mine" if mine else "w-theirs"}">'
            f'<div class="w-msg-meta">#{esc(ref)} · {esc(message.get("timestamp"))} · {who} {tags}</div>'
            f'<div class="w-msg-body">{esc(body)}</div></div>')


def client_header_html(client, open_count, owed_amount):
    name = client.get("name") or "Unknown client"
    phone = f'<div class="w-caption">{esc(client["phone"])}</div>' if client.get("phone") else ""
    owed = badge(f"Owes {fmt_mad(owed_amount)}") if owed_amount else badge("Nothing owed")
    return (f'<div class="w-client-head"><span class="w-avatar w-avatar-lg">{esc(initials(name))}</span>'
            f'<div><div class="w-client-name">{esc(name)}</div>{phone}</div>'
            f'{badge(f"{open_count} open items")}{owed}</div>')


def notice_html(text):
    return f'<div class="w-notice"><b>Human in control.</b> {esc(text)}</div>'


def quote_html(text):
    return f'<div class="w-quote">{esc(text)}</div>'


def empty_html(text):
    return f'<div class="w-empty">{esc(text)}</div>'
