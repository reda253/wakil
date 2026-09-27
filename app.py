"""Wakil: Streamlit entry point and router.  Owner: D4.  Run: streamlit run app.py"""
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from ui.theme import apply_theme

load_dotenv()
LOGO = str(Path(__file__).parent / "ui" / "assets" / "logo.png")

st.set_page_config(page_title="Wakil", page_icon=LOGO, layout="wide")
apply_theme()
st.logo(LOGO, size="large")

page = st.navigation(
    [
        st.Page("pages/2_Dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
        st.Page("pages/5_Orders.py", title="Orders", icon=":material/inventory_2:"),
        st.Page("pages/3_Client.py", title="Clients & history", icon=":material/group:"),
        st.Page("pages/4_Brief_Reply.py", title="Brief & reply", icon=":material/edit_note:"),
        st.Page("pages/1_Import.py", title="Import chat", icon=":material/upload_file:"),
    ],
    position="top",
)
page.run()
