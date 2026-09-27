"""Clients & history.  Owner: D4."""
import streamlit as st

from core import db
from ui import components as ui
from ui import html as h
from ui import viewmodel as vm

today = vm.today()
st.title("Clients & history")

clients = db.get_clients()
if not clients:
    ui.empty_state("No clients yet. Open 'Import chat' in the top menu to add your first WhatsApp chat.")
    st.stop()

ids = [c["id"] for c in clients]
by_id = {c["id"]: c for c in clients}
if st.session_state.get("client_page_client") not in ids:
    imported = st.session_state.get("client_id")
    st.session_state["client_page_client"] = imported if imported in ids else ids[0]
cid = st.selectbox("Client", ids, format_func=lambda i: by_id[i]["name"], key="client_page_client")

items = db.get_items(cid, status=None)
open_items = [i for i in items if i.get("status") == "open"]
with st.container(border=True):
    st.html(h.client_header_html(by_id[cid], len(open_items), vm.client_owes(items, cid)))

tab_items, tab_history = st.tabs([f"Items ({len(open_items)} open)", "Message history"])
with tab_items:
    show_done = st.toggle("Show done items", key="client_show_done")
    shown = vm.sort_by_due(items if show_done else open_items)
    if not shown:
        ui.empty_state("No open items for this client.")
    for item in shown:
        ui.item_card(item, None, today, key_prefix="client_item")
with tab_history:
    ui.message_history(db.get_messages(cid))
