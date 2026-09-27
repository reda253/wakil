"""Client page.  Owner: D4."""
import streamlit as st

from core import db
from ui.components import item_card

st.title("Client")

# STUB: summary, message history with transcripts
client = st.selectbox("Client", db.get_clients(), format_func=lambda c: c["name"])
for item in db.get_items(client["id"], status=None):
    item_card(item)
