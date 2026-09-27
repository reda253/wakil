import os
import tempfile

import streamlit as st

import ai
import db
import parser as wa_parser
import speech

st.title(" Importer une discussion")
st.caption(
    " Consentement : une exportation contient aussi les messages de ton client. "
    "Informe-le avant d'utiliser Wakil. Les numéros sont masqués et l'audio est supprimé après transcription."
)

uploaded = st.file_uploader("Export WhatsApp (.txt ou .zip avec notes vocales)", type=["txt", "zip"])
my_name = st.text_input("Ton nom tel qu'il apparaît dans la discussion")

if uploaded and st.button("Analyser", type="primary"):
    progress = st.progress(0, text="Lecture de l'export…")
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as f:
        f.write(uploaded.getbuffer())
        path = f.name

    client_name, messages = wa_parser.parse_export(path, my_name=my_name or None)

    voice = [m for m in messages if m["type"] == "voice" and not m.get("transcript")]
    for n, m in enumerate(voice, 1):
        progress.progress(0.2 + 0.5 * n / max(len(voice), 1), text=f"Transcription {n}/{len(voice)}…")
        m["transcript"] = speech.transcribe(m["content"])["text"]

    progress.progress(0.8, text="Extraction…")
    result = ai.extract_items(client_name, messages)

    client_id = db.save_client(client_name, summary=result["client_summary"])
    db.save_messages(client_id, messages)
    db.save_items(client_id, result["items"])
    progress.progress(1.0, text="Terminé")
    st.success(f"{len(result['items'])} éléments extraits pour {client_name}.")
    st.session_state["client_id"] = client_id
    st.page_link("pages/3_Client.py", label="Voir la fiche client", icon="👤")
