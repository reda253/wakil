"""Reusable UI pieces.  Owner: D4.

Styled static parts come from ui.html (escaped); interaction uses native widgets.
LLM calls happen only on explicit user action and are cached in st.session_state.
"""
import streamlit as st

from core import ai, db
from ui import html as h
from ui import viewmodel as vm

NEVER_SENDS = "Wakil never sends messages on your behalf. You review, copy and send."


def empty_state(text):
    st.html(h.empty_html(text))


def money_badge(amount):
    st.metric("Owed to me", vm.fmt_mad(amount))


def detail_list(pairs):
    st.html(h.kv_html(pairs))


# ---------- items ----------

def _source(item):
    """Source message of an item, looked up inside the item's own client.

    source_message_id is a per-chat local_id, so without client_id the lookup can
    land on another client's message with the same local_id.
    """
    ref = (item or {}).get("source_message_id")
    return db.get_message(ref, client_id=item.get("client_id")) if ref is not None else None


def _toggle_done(item_id, key):
    db.set_item_status(item_id, "done" if st.session_state[key] else "open")


def _source_view(src):
    if not src:
        st.warning("Source message not found.")
        return
    who = "You" if src.get("sender") in ("owner", "me") else "Client"
    kind = "Voice note" if src.get("type") == "voice" else "Text"
    via = "WhatsApp live" if src.get("source") == "whatsapp" else "Chat export"
    ref = src.get("local_id", src.get("id"))
    st.caption(f"#{ref} · {src.get('timestamp', '')} · {who} · {kind} · {via}")
    st.html(h.quote_html(src.get("transcript") or src.get("content") or "(empty message)"))


def item_card(item, client_name=None, today=None, key_prefix="item", urgency=None):
    today = today or vm.today()
    src = _source(item)
    key = f"{key_prefix}_done_{item['id']}"
    with st.container(border=True):
        left, mid, right = st.columns([0.07, 0.71, 0.22], vertical_alignment="center")
        left.checkbox("Done", value=item.get("status") == "done", key=key, label_visibility="collapsed",
                      on_change=_toggle_done, args=(item["id"], key))
        mid.html(h.item_html(item, client_name, today, source=(src or {}).get("source"), urgency=urgency))
        with right.popover("Source", icon=":material/chat:"):
            _source_view(src)


# ---------- metric cards ----------

def metric_card(icon, label, value, unit, details):
    with st.container(border=True):
        st.html(h.metric_html(icon, label, value, unit))
        with st.popover("Details", icon=":material/expand_more:"):
            details()


def metric_row(items, owed, clients, today):
    m = vm.dashboard_metrics(items, owed, clients, today)
    names = {c["id"]: c["name"] for c in clients}
    order_rows = vm.orders(items, clients, today)
    owed_rows = vm.owed_rows(owed, items, clients, today)

    def owed_details():
        st.markdown(f"**{vm.fmt_mad(m['owed_overdue'])}** overdue · **{m['owed_clients']}** clients")
        if owed_rows:
            detail_list([(r["client"], f"{vm.fmt_mad(r['amount_mad'])} · {r['due_label']}") for r in owed_rows])

    def orders_details():
        c = vm.urgency_counts(order_rows)
        st.markdown(" · ".join(f"**{c[u]}** {vm.URGENCY_LABELS[u].lower()}" for u in vm.URGENCY))
        st.caption("The Orders page in the top menu lists them all.")

    def promises_details():
        st.markdown(f"**{m['promises_mine']}** made by you · **{m['promises_client']}** made by clients")
        proms = vm.sort_by_due([i for i in items if i.get("type") == "promise"])
        if proms:
            detail_list([(names.get(i.get("client_id"), "Unknown client"), i.get("description", "")) for i in proms])

    def verify_details():
        low = vm.sort_by_due([i for i in items if i.get("confidence") == "low"])
        if not low:
            st.caption("Nothing to check. Every open item was stated clearly.")
            return
        st.caption("Wakil was not sure about these. Open the source and confirm.")
        detail_list([(names.get(i.get("client_id"), "Unknown client"), i.get("description", "")) for i in low])

    cols = st.columns(4)
    with cols[0]:
        metric_card("payments", "Owed to you", f"{m['owed_total']:,.0f}", "MAD", owed_details)
    with cols[1]:
        metric_card("inventory_2", "Open orders", m["orders"], "", orders_details)
    with cols[2]:
        metric_card("handshake", "Promises tracked", m["promises"], "", promises_details)
    with cols[3]:
        metric_card("fact_check", "Need a check", m["to_verify"], "", verify_details)


# ---------- money owed ----------

def _prefill_brief(brief_key, client_id):
    st.session_state[f"{brief_key}_client"] = client_id
    st.session_state[f"{brief_key}_goal"] = "payment_reminder"
    st.session_state[f"{brief_key}_autogen"] = True


def owed_list(rows, brief_key):
    if not rows:
        empty_state("Nobody owes you money right now.")
        return
    st.caption(f"Total {vm.fmt_mad(sum(r['amount_mad'] for r in rows))}")
    for n, row in enumerate(rows):
        with st.container(border=True):
            st.html(h.owed_row_html(row))
            a, b = st.columns(2)
            a.button("Urgent follow-up" if row["overdue"] else "Draft reminder", key=f"owed_{n}_draft",
                     type="primary" if row["overdue"] else "secondary", icon=":material/edit:",
                     disabled=row["client_id"] is None, on_click=_prefill_brief, args=(brief_key, row["client_id"]))
            if row["item"]:
                with b.popover("Source", icon=":material/chat:"):
                    _source_view(_source(row["item"]))


# ---------- priority board ----------

def priority_board(items, client_names, today, key):
    if not items:
        empty_state("No open items. Import a chat to get started.")
        return
    counts = vm.bucket_counts(items, today)
    bucket = st.segmented_control(
        "Show", vm.BUCKETS, format_func=lambda b: f"{vm.BUCKET_LABELS[b]} ({counts[b]})",
        default="all", key=f"{key}_bucket", label_visibility="collapsed") or "all"
    shown = vm.filter_items(items, bucket, today)
    if not shown:
        empty_state(f"Nothing in '{vm.BUCKET_LABELS[bucket]}'.")
        return
    for item in shown:
        item_card(item, client_names.get(item.get("client_id")), today, key_prefix=f"{key}_item")


# ---------- brief & reply ----------

def brief_panel(clients, key):
    if not clients:
        empty_state("No clients yet. Import a WhatsApp chat first.")
        return
    ids = [c["id"] for c in clients]
    by_id = {c["id"]: c for c in clients}
    sel_key = f"{key}_client"
    if st.session_state.get(sel_key) not in ids:
        st.session_state[sel_key] = ids[0]
    cid = st.selectbox("Client", ids, format_func=lambda i: by_id[i]["name"], key=sel_key)
    name = by_id[cid]["name"]

    briefs = st.session_state.setdefault("briefs", {})
    drafts = st.session_state.setdefault("drafts", {})
    clicked = st.button("Refresh brief" if cid in briefs else f"Prepare my call with {name}",
                        key=f"{key}_gen", type="primary", icon=":material/auto_awesome:")
    if clicked or st.session_state.pop(f"{key}_autogen", False):
        with st.spinner("Reading this client's items and last messages..."):
            try:
                briefs[cid] = ai.make_brief(name, db.get_items(cid), db.get_messages(cid, limit=20))
                for k in [k for k in drafts if k[0] == cid]:
                    del drafts[k]
            except Exception as e:  # an LLM/network failure must never crash the page
                st.error(f"Could not prepare the brief right now. Please try again. ({type(e).__name__})")

    brief = briefs.get(cid)
    if not brief:
        st.caption("Wakil reads this client's items and last 20 messages, then writes a 5-line summary.")
        st.html(h.notice_html(NEVER_SENDS))
        return
    st.html(h.brief_html(vm.parse_brief(brief)))

    st.caption("Draft a reply")
    goal = st.segmented_control("Goal", list(vm.GOALS), format_func=vm.GOALS.get,
                                key=f"{key}_goal", label_visibility="collapsed")
    if goal and (cid, goal) not in drafts:
        with st.spinner("Writing the draft..."):
            try:
                drafts[(cid, goal)] = ai.draft_reply(brief, goal)
            except Exception as e:
                st.error(f"Could not write the draft right now. Please try again. ({type(e).__name__})")
    draft = drafts.get((cid, goal)) if goal else None
    if draft:
        st.caption("WhatsApp (copy with the icon on the right)")
        st.code(draft.get("whatsapp", ""), language=None, wrap_lines=True)
        st.link_button("Open in WhatsApp", vm.whatsapp_link(draft.get("whatsapp", ""), by_id[cid].get("phone")),
                       type="primary", icon=":material/send:")
        st.caption("Email")
        st.code(draft.get("email", ""), language=None, wrap_lines=True)
    st.html(h.notice_html(NEVER_SENDS))


def message_history(messages):
    if not messages:
        empty_state("No messages for this client yet.")
        return
    st.html("".join(h.message_html(m) for m in messages))
