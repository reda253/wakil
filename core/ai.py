"""Extraction, brief, draft reply.  Owner: P2.

Primary LLM: Gemini Flash (JSON mode). Fallback: Groq-hosted model / NVIDIA Build, behind call_llm().
Messages go to the model as numbered lines: "[12] 2026-09-27 14:32 client: ..."
Validate JSON; drop items whose source_message_id is not in the input; retry once with the error.
Chunk long chats (~150 messages), merge, dedupe.
"""

ITEM_TYPES = {"task", "promise", "payment", "deadline", "question"}


def call_llm(prompt, json_mode=False):
    """Try Gemini, then fallback provider. Return (text, provider)."""
    raise NotImplementedError


def extract_items(client_name, messages):
    """Return {"client_summary": str, "items": list[Item]}.

    Item = {"type": ..., "description": str, "owner": "me"|"client",
            "amount_mad": float|None, "due_date": "YYYY-MM-DD"|None,
            "source_message_id": int, "confidence": "high"|"low"}
    """
    # STUB
    return {
        "client_summary": "Ahmed veut une cuisine complète à 15000 MAD. Avance de 50% promise pour vendredi.",
        "items": [
            {"type": "payment", "description": "Avance de 50% (7500 MAD) à recevoir", "owner": "client",
             "amount_mad": 7500.0, "due_date": "2026-09-26", "source_message_id": 3, "confidence": "high"},
            {"type": "deadline", "description": "Livrer la cuisine sous 15 jours", "owner": "me",
             "amount_mad": None, "due_date": "2026-10-05", "source_message_id": 2, "confidence": "low"},
        ],
    }


def make_brief(client_name, items, recent_messages):
    """5 lines max: status, my promises, client's promises, money owed, next step."""
    # STUB
    return (
        f"Situation : cuisine complète pour {client_name}, prix 15000 MAD.\n"
        "Mes promesses : livraison sous 15 jours.\n"
        "Promesses du client : avance de 7500 MAD vendredi.\n"
        "Argent dû : 7500 MAD (avance non reçue).\n"
        "Prochaine étape : rappeler l'avance avant de commencer."
    )


def draft_reply(brief, goal, language="darija"):
    """Return {"whatsapp": str, "email": str}. The app NEVER sends anything."""
    # STUB
    return {
        "whatsapp": "Salam Ahmed, ghir bach nfakrek b l'avance dyal 7500 dh bach nbdaw lkhdma. Chokran!",
        "email": "Bonjour Ahmed,\n\nJe me permets de vous rappeler l'avance de 7500 MAD convenue "
                 "afin de lancer la fabrication.\n\nCordialement.",
    }
