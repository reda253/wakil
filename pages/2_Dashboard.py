"""Dashboard.  Owner: D4."""
import streamlit as st

from core import db
from ui.components import item_card, money_badge

st.title("Dashboard")

# STUB: sort by due date, overdue in red
owed = db.get_money_owed()
money_badge(sum(o["amount_mad"] for o in owed))
for o in owed:
    st.write(f"{o['client']}: {o['amount_mad']:,.0f} MAD")

st.subheader("Open items")
for item in db.get_items():
    item_card(item)
