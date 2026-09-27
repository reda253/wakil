"""Wakil: Streamlit entry point.  Owner: D4.  Run: streamlit run app.py"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Wakil", layout="wide")
st.title("Wakil")
st.write("Turns your WhatsApp chats and voice notes into tasks, deadlines, promises and payments owed.")
st.info("Wakil never sends messages on your behalf.")
st.page_link("pages/1_Import.py", label="1. Import a chat")
st.page_link("pages/2_Dashboard.py", label="2. Dashboard")
st.page_link("pages/3_Client.py", label="3. Client")
st.page_link("pages/4_Brief_Reply.py", label="4. Brief & reply")
