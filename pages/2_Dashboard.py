from datetime import date

import streamlit as st

import db

st.title(" Tableau de bord")

items = db.get_items()
owed = [i for i in items if i["type"] == "payment" and i["owner"] == "client" and i["amount_mad"]]

st.subheader(" Qui me doit de l'argent")
if owed:
    st.metric("Total dû", f"{sum(i['amount_mad'] for i in owed):,.0f} MAD")
    for i in owed:
        st.write(f"**{i['client_name']}** · {i['amount_mad']:,.0f} MAD · {i['description']}")
else:
    st.write("Personne ne te doit d'argent.")

st.subheader("Tâches et rappels")
today = date.today().isoformat()
for i in items:
    overdue = i["due_date"] and i["due_date"] < today
    tag = "" if overdue else ("" if i["confidence"] == "low" else "")
    st.write(f"{tag} `{i['due_date'] or '—'}` **{i['client_name']}** · {i['type']} · {i['description']}")
