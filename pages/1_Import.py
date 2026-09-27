"""Import page.  Owner: D3.

Uploads a WhatsApp export and hands it to core.pipeline.  The page owns no logic
beyond presentation: parsing, transcription and extraction all live in pipeline
so the same code path serves the live WhatsApp path.
"""
import os
import shutil
import tempfile

import streamlit as st

from core import db, pipeline

st.title("Import a chat")
st.caption(
    "An export contains your client's messages too. Tell them before you use "
    "Wakil. Phone numbers are masked and voice notes are deleted once transcribed.")

uploaded = st.file_uploader("WhatsApp export (.zip or .txt)", type=["zip", "txt"])
owner_name = st.text_input("Your name in the chat")
client_name = st.text_input("Client name", help="Leave empty to use the name in the export.")
client_phone = st.text_input("Client phone (optional)")
consent = st.checkbox("I have informed my clients")

STAGE_FRACTION = {
    "Unpacking export": 0.05,
    "Parsing chat": 0.15,
    "Saving messages": 0.30,
    "Extracting items": 0.85,
    "Saving items": 0.95,
}

ready = bool(uploaded and owner_name.strip() and consent)
if not ready and not uploaded:
    st.info("Export a chat from WhatsApp (chat > ⋮ > Export chat > 'Attach media') "
            "and upload the .zip here.")

if st.button("Analyze", type="primary", disabled=not ready):
    status = st.empty()
    bar = st.progress(0.0)

    def on_progress(stage, current=None, total=None):
        if stage == "Transcribing" and total:
            bar.progress(0.35 + 0.45 * (current or 0) / total,
                         text=f"Transcribing {current}/{total}…")
            status.caption(stage)
        else:
            bar.progress(STAGE_FRACTION.get(stage, 0.05), text=stage)
            status.caption(stage)

    tmp_dir = tempfile.mkdtemp(prefix="wakil_import_")
    try:
        ext = ".zip" if uploaded.name.lower().endswith(".zip") else ".txt"
        tmp_path = os.path.join(tmp_dir, f"upload{ext}")
        with open(tmp_path, "wb") as fh:
            fh.write(uploaded.getbuffer())

        client_id = pipeline.process_export(
            tmp_path,
            owner_name.strip(),
            client_name.strip() or None,
            client_phone.strip() or None,
            progress_cb=on_progress,
        )
    except Exception as exc:
        st.error(f"Import failed: {exc}")
    else:
        bar.progress(1.0, text="Done")
        client = db.get_client(client_id) or {}
        items = db.get_items(client_id, status="open")
        voice = [m for m in db.get_messages(client_id) if m["type"] == "voice"]
        transcribed = [m for m in voice if (m["transcript"] or "").strip()]

        st.success(
            f"Imported {len(items)} open item(s) for {client.get('name', 'the client')} "
            f"· {len(voice)} voice note(s), {len(transcribed)} transcribed.")

        for warning in pipeline.get_warnings(client_id):
            st.warning(warning)

        st.session_state["client_id"] = client_id
        st.page_link("pages/3_Client.py", label="Open the client page", icon="\U0001F464")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
