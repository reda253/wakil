"""Dashboard.  Owner: D4."""
import streamlit as st

from core import db
from ui import components as ui
from ui import viewmodel as vm

today = vm.today()
clients = db.get_clients()
names = {c["id"]: c["name"] for c in clients}
items = db.get_items()          # open items, all clients
owed = db.get_money_owed()

st.title("Dashboard")
st.caption(f"{len(clients)} clients · {len(items)} open items · every item links back to its source message")

ui.metric_row(items, owed, clients, today)

left, right = st.columns([7, 5], gap="large")
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
