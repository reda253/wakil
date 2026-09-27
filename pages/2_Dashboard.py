"""Dashboard.  Owner: D4."""
import streamlit as st

from core import db
from ui import components as ui
from ui import html as h
from ui import viewmodel as vm

today = vm.today()
clients = db.get_clients()
names = {c["id"]: c["name"] for c in clients}
items = db.get_items()          # open items, all clients
owed = db.get_money_owed()
metrics = vm.dashboard_metrics(items, owed, clients, today)

with st.container(key="hero"):
    st.html(h.hero_html(f"{vm.long_date(today)} · {len(clients)} clients", vm.headline(metrics)))
    ui.metric_row(items, owed, clients, today)

left, right = st.columns([7, 5], gap="medium")
with left:
    with st.container(border=True):
        st.subheader("Who owes me money", anchor=False)
        ui.owed_list(vm.owed_rows(owed, items, clients, today), brief_key="dash")
    with st.container(border=True):
        st.subheader("Priority board", anchor=False)
        st.caption("Earliest first. Tick an item when it is done.")
        ui.priority_board(items, names, today, key="dash")
with right:
    with st.container(border=True):
        st.subheader("Pre-call brief & reply", anchor=False)
        ui.brief_panel(clients, key="dash")
    with st.container(border=True):
        st.subheader("Next to deliver", anchor=False)
        ui.next_to_deliver(vm.orders(items, clients, today))
