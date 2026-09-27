"""Wakil — Streamlit entry point.  Owner: P3.  Run: streamlit run app.py"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Wakil", page_icon="", layout="wide")

st.title("Wakil · وكيل")
st.write(
    "Transforme tes discussions WhatsApp et notes vocales en tâches, échéances, promesses et paiements."
)
st.info("Wakil n'envoie jamais de message à ta place. Tu relis et tu envoies toi-même.")
st.page_link("pages/1_Import.py", label="1. Importer une discussion", icon="")
st.page_link("pages/2_Dashboard.py", label="2. Tableau de bord", icon="")
st.page_link("pages/3_Client.py", label="3. Fiche client", icon="👤")
st.page_link("pages/4_Brief_and_Reply.py", label="4. Brief & réponse", icon="")