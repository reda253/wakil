import streamlit as st

import db

st.title("👤 Fiche client")

clients = db.get_clients()
if not clients:
    st.info("Aucun client. Importe une discussion d'abord.")
    st.stop()

ids = [c["id"] for c in clients]
default = ids.index(st.session_state["client_id"]) if st.session_state.get("client_id") in ids else 0
client = st.selectbox("Client", clients, index=default, format_func=lambda c: c["name"])
st.session_state["client_id"] = client["id"]

if client["summary"]:
    st.write(client["summary"])

for item in db.get_items(client["id"], status=None):
    cols = st.columns([0.08, 0.72, 0.2])
    done = cols[0].checkbox("fait", value=item["status"] == "done", key=f"done_{item['id']}",
                            label_visibility="collapsed")
    if done != (item["status"] == "done"):
        db.set_item_status(item["id"], "done" if done else "open")
    color = "orange" if item["confidence"] == "low" else "blue"
    amount = f" · {item['amount_mad']:,.0f} MAD" if item["amount_mad"] else ""
    cols[1].markdown(
        f":{color}[**{item['type']}**] {item['description']}{amount} · `{item['due_date'] or '—'}`"
        + (" · _à vérifier_" if item["confidence"] == "low" else "")
    )
    with cols[2].popover("Voir la source"):
        src = db.get_source_message(client["id"], item["source_message_id"])
        if src:
            st.caption(f"[{src['local_id']}] {src['timestamp']} · {src['sender']}")
            st.write(src["transcript"] or src["content"])
        else:
            st.warning("Message source introuvable.")
