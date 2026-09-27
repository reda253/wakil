"""Brief & reply page.  Owner: D4."""
import streamlit as st

from core import ai, db

st.title("Brief & reply")
st.info("Wakil never sends messages on your behalf.")

# STUB: goal buttons, copy buttons
client = st.selectbox("Client", db.get_clients(), format_func=lambda c: c["name"])
if st.button("Prepare my call"):
    brief = ai.make_brief(client["name"], db.get_items(client["id"]), db.get_messages(client["id"], limit=20))
    st.text(brief)
    draft = ai.draft_reply(brief, "payment_reminder")
    st.code(draft["whatsapp"], language=None)
    st.code(draft["email"], language=None)
