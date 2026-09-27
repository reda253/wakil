"""Orders (commandes): what each client is waiting for, most urgent first.  Owner: D4.

An order is an open task/promise/deadline the owner must deliver (see ui.viewmodel.orders).
Urgency comes from the due date only: Urgent overdue, High today/tomorrow, Normal <= 7 days, Low later.
"""
import streamlit as st

from core import db
from ui import components as ui
from ui import viewmodel as vm

today = vm.today()
st.title("Orders")
st.caption("What you promised to deliver, who is waiting for it, and how urgent it is.")

clients = db.get_clients()
names = {c["id"]: c["name"] for c in clients}
rows = vm.orders(db.get_items(), clients, today)
if not rows:
    ui.empty_state("No open orders. Promises and tasks you owe clients will appear here after an import.")
    st.stop()

counts = vm.urgency_counts(rows)
f1, f2 = st.columns([3, 2], vertical_alignment="center")
level = f1.segmented_control(
    "Urgency", ("all", *vm.URGENCY), format_func=lambda u: f"{vm.URGENCY_LABELS[u]} ({counts[u]})",
    default="all", key="orders_level", label_visibility="collapsed") or "all"
client_id = f2.selectbox("Client", [None, *names], format_func=lambda i: "All clients" if i is None else names[i],
                         key="orders_client", label_visibility="collapsed")

shown = [r for r in rows
         if (level == "all" or r["urgency"] == level) and (client_id is None or r["client_id"] == client_id)]
if not shown:
    ui.empty_state("No orders match these filters.")
for r in shown:
    who = r["client"] + (f" · still owes {vm.fmt_mad(r['client_owes'])}" if r["client_owes"] else "")
    ui.item_card(r["item"], who, today, key_prefix="orders_item", urgency=r["urgency"])
