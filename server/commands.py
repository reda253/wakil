"""Bot commands as pure functions (testable without WhatsApp).  Owner: D2.

client <name> | brief <name> | tasks | help | anything else -> pipeline.process_live_message
"""
from core import db, ai, pipeline

# In-memory active client per sender phone number
_active_client: dict[str, str] = {}


def get_active_client(sender: str) -> str:
    return _active_client.get(sender, "")


def handle(sender: str, body: str) -> str:
    """Return the reply text for an incoming text message."""
    text = (body or "").strip()
    lower = text.lower()

    if not text:
        return "Please send a command or forward a message. Type *help* for options."

    # 1. client <name>
    if lower.startswith("client "):
        name = text[7:].strip()
        if not name:
            return "Usage: *client <name>* (e.g., `client Ahmed`)"
        _active_client[sender] = name
        db.get_or_create_client(name)
        return f"✅ Now filing messages under client *{name}*."

    # 2. brief <name> or brief (uses active client)
    if lower.startswith("brief"):
        parts = text.split(maxsplit=1)
        name = parts[1].strip() if len(parts) > 1 else _active_client.get(sender)
        if not name:
            return "Which client would you like a brief for? Send: *brief <name>*"
        client_id = db.get_or_create_client(name)
        items = db.get_items(client_id=client_id, status="open")
        messages = db.get_messages(client_id=client_id, limit=30)
        return ai.make_brief(name, items, messages)

    # 3. tasks
    if lower == "tasks":
        items = db.get_items(status="open")
        if not items:
            return "No open tasks across any clients! 🎉"
        lines = ["📋 *Open Tasks:*"]
        for it in sorted(items, key=lambda x: (x.get("due_date") or "9999", x.get("client_name", ""))):
            due = f" (due {it['due_date']})" if it.get("due_date") else ""
            client = f" [{it.get('client_name', 'Client')}]"
            lines.append(f"•{client} {it['description']}{due}")
        return "\n".join(lines)

    # 4. help
    if lower == "help":
        return (
            "🤖 *Wakil Bot Commands:*\n"
            "• *client <name>* — set active client for incoming messages\n"
            "• *brief <name>* — generate 5-line pre-call brief\n"
            "• *tasks* — view all open tasks across clients\n"
            "• *help* — show this command list\n\n"
            "💡 *Forward any message or voice note* after setting a client to extract tasks & payments."
        )

    # 5. Anything else -> process as live message for active client
    active = _active_client.get(sender)
    if not active:
        return "Which client is this message about? Please send: *client <name>* first."

    new_items = pipeline.process_live_message(active, msg_type="text", content=text)
    if not new_items:
        return f"✅ Noted for *{active}* (no new action items found)."

    lines = [f"✅ Noted for *{active}*:"]
    for it in new_items[:5]:
        due = f" · due {it['due_date']}" if it.get("due_date") else ""
        amt = f" · 💰 {it['amount_mad']:,.0f} MAD" if it.get("amount_mad") else ""
        lines.append(f"• [{it['type'].upper()}] {it['description']}{due}{amt}")
    return "\n".join(lines)

