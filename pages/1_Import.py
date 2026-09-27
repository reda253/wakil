"""Import page.  Owner: D3."""
import streamlit as st

from core import pipeline

st.title("Import a chat")

uploaded = st.file_uploader("WhatsApp export (.zip or .txt)", type=["zip", "txt"])
owner_name = st.text_input("Your name in the chat")
client_name = st.text_input("Client name")
client_phone = st.text_input("Client phone (optional)")
consent = st.checkbox("I have informed my clients")

# STUB: save upload, show progress (parsing -> transcribing X/Y -> extracting)
if st.button("Analyze", disabled=not (uploaded and consent)):
    client_id = pipeline.process_export("", owner_name, client_name, client_phone or None)
    st.success("Done.")
    st.page_link("pages/3_Client.py", label="Open the client page")
