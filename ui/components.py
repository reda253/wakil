"""Reusable UI pieces.  Owner: D4."""
import streamlit as st

from core import db


def item_card(item):
    """Colored tag by type, orange if low confidence, WhatsApp badge, view source, done checkbox."""
    # STUB
    low = " · :orange[please verify]" if item["confidence"] == "low" else ""
    amount = f" · {item['amount_mad']:,.0f} MAD" if item["amount_mad"] else ""
    st.markdown(f"**{item['type']}** · {item['description']}{amount} · `{item['due_date'] or '-'}`{low}")
    with st.expander("View source"):
        src = db.get_message(item["source_message_id"])
        st.write((src["transcript"] or src["content"]) if src else "Source not found.")


def money_badge(amount):
    st.metric("Owed to me", f"{amount:,.0f} MAD")


def empty_state(text):
    st.info(text)
