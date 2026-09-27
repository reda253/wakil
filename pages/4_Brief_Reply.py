"""Brief & reply.  Owner: D4."""
import streamlit as st

from core import db
from ui import components as ui

st.title("Brief & reply")
st.caption("Before you call a client: a 5-line summary, then a ready-to-copy WhatsApp message and email.")

_, center, _ = st.columns([1, 3, 1])
with center:
    with st.container(border=True):
        ui.brief_panel(db.get_clients(), key="page")
