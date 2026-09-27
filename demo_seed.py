"""
Demo seed script — run this once to populate the dashboard with realistic data.

Usage:
    python demo_seed.py

This simulates 3 clients sending WhatsApp messages. The AI pipeline extracts
tasks, payments, and deadlines exactly as it would from a real voice/text message.
"""
from dotenv import load_dotenv
load_dotenv()

from core import pipeline

print("Seeding demo data into Wakil...\n")

# -- Client 1: Karim - owes money, has a delivery due -----------------------
print("Processing messages from Karim...")
pipeline.process_live_message(
    client_name="Karim Benali",
    msg_type="text",
    content="Salam, je vais venir chercher les 3 tables basse demain. "
            "Je vous envoie les 2000 DH restants ce soir par CIH."
)

# -- Client 2: Fatima - wants a quote, promised a deposit -------------------
print("Processing messages from Fatima...")
pipeline.process_live_message(
    client_name="Fatima Zahra",
    msg_type="text",
    content="Bonjour, j'ai besoin d'une commande de 6 chaises en bois pour "
            "ma boutique. Vous pouvez livrer avant le 5 octobre? "
            "Je peux payer 50% maintenant, soit 3600 DH."
)

# -- Client 3: Omar - late payment, urgent follow-up ------------------------
print("Processing messages from Omar...")
pipeline.process_live_message(
    client_name="Omar Tazi",
    msg_type="text",
    content="Bonsoir, désolé pour le retard. Je dois encore 1500 DH pour "
            "la bibliothèque. Je règle ça vendredi sans faute. "
            "Au fait, vous avez les meubles TV en stock?"
)

print("\nDone! Refresh your Streamlit dashboard to see the data.")
print("   http://localhost:8501")
