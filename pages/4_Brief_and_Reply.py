import streamlit as st

import ai
import db

st.title("Brief & réponse")
st.info("Wakil n'envoie jamais de message à ta place. Copie le brouillon et envoie-le toi-même.")

clients = db.get_clients()
if not clients:
    st.info("Aucun client. Importe une discussion d'abord.")
    st.stop()

client = st.selectbox("Client", clients, format_func=lambda c: c["name"])

if st.button(f"Préparer mon appel avec {client['name']}", type="primary"):
    items = db.get_items(client["id"])
    recent = db.get_messages(client["id"])[-20:]
    st.session_state["brief"] = ai.make_brief(client["name"], items, recent)

brief = st.session_state.get("brief")
if brief:
    st.subheader("Brief")
    st.text(brief)

    language = st.radio("Langue", ["darija", "français"], horizontal=True)
    goals = ["Rappel de paiement", "Confirmer la date de livraison", "Relance du devis"]
    cols = st.columns(len(goals))
    for col, goal in zip(cols, goals):
        if col.button(goal):
            st.session_state["draft"] = ai.draft_reply(brief, goal, language)

    draft = st.session_state.get("draft")
    if draft:
        st.subheader("WhatsApp")
        st.code(draft["whatsapp"], language=None)
        st.subheader("Email")
        st.code(draft["email"], language=None)
