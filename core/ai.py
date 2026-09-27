"""Extraction, brief, draft reply.  Owner: D1.  Prompts live in prompts/."""


def extract_items(client_name, messages, existing_items=[]):
    """Return {"summary": str, "items": list[Item]} (only NEW items if existing_items given)."""
    # STUB
    return {
        "summary": f"{client_name} ordered a full kitchen for 15,000 MAD. 50% deposit promised for Friday.",
        "items": [
            {"id": 0, "client_id": 0, "type": "payment", "description": "50% deposit (7,500 MAD) to receive",
             "owner": "client", "amount_mad": 7500.0, "due_date": "2026-09-26", "source_message_id": 3,
             "confidence": "high", "status": "open"},
            {"id": 0, "client_id": 0, "type": "deadline", "description": "Deliver the kitchen within 15 days",
             "owner": "me", "amount_mad": None, "due_date": "2026-10-05", "source_message_id": 2,
             "confidence": "low", "status": "open"},
        ],
    }


def make_brief(client_name, items, recent_messages):
    """5 lines max: status, my promises, client's promises, money owed, next step."""
    # STUB
    return (
        f"Status: full kitchen for {client_name}, 15,000 MAD.\n"
        "My promises: delivery within 15 days.\n"
        "Client's promises: 7,500 MAD deposit on Friday.\n"
        "Money owed: 7,500 MAD (deposit not received).\n"
        "Next step: remind about the deposit before starting."
    )


def draft_reply(brief, goal):
    """goal: payment_reminder | confirm_delivery | quote_followup | thank_you.
    Return {"whatsapp": str, "email": str}."""
    # STUB
    return {
        "whatsapp": "Hi Ahmed, just a reminder about the 7,500 MAD deposit so we can start. Thanks!",
        "email": "Dear Ahmed,\n\nThis is a reminder about the agreed 7,500 MAD deposit so we can start "
                 "production.\n\nBest regards.",
    }
