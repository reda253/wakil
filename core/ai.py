"""Extraction, brief, and draft reply AI engine. Owner: D1.

Prompts live in prompts/ directory and use .replace() for safe interpolation.
"""
import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from core.contracts import Item, Message
from core import llm

logger = logging.getLogger("wakil.ai")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def _read_prompt(filename: str) -> str:
    """Read prompt file safely without formatting."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _format_messages_for_prompt(messages: List[Message]) -> str:
    """Format messages into numbered lines: [id] YYYY-MM-DD HH:MM sender: text."""
    lines = []
    for msg in messages:
        msg_id = msg.get("id", 0)
        ts = msg.get("timestamp", "")
        # normalize sender label: "owner" -> "me" for clear perspective in prompts
        sender_raw = msg.get("sender", "client")
        sender = "me" if sender_raw in ("owner", "me") else "client"
        content = msg.get("transcript") or msg.get("content") or ""
        lines.append(f"[{msg_id}] {ts} {sender}: {content}")
    return "\n".join(lines)


def _validate_and_sanitize_items(
    raw_items: List[Dict[str, Any]],
    valid_message_ids: set,
    client_id: int = 0
) -> List[Item]:
    """Ensure every extracted item strictly satisfies the Item contract."""
    sanitized: List[Item] = []
    valid_types = {"task", "promise", "payment", "deadline", "question"}
    valid_owners = {"me", "client"}
    valid_confidences = {"high", "low"}

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        item_type = str(raw.get("type", "task")).lower().strip()
        if item_type not in valid_types:
            item_type = "task"

        description = str(raw.get("description", "")).strip()
        if not description:
            continue

        owner_raw = str(raw.get("owner", "me")).lower().strip()
        owner = "me" if owner_raw in ("me", "owner") else "client"

        # Sanitize amount_mad
        amount_mad: Optional[float] = None
        raw_amount = raw.get("amount_mad")
        if raw_amount is not None:
            try:
                # Handle numeric string or float
                cleaned = re.sub(r"[^\d.]", "", str(raw_amount))
                if cleaned:
                    amount_mad = float(cleaned)
            except Exception:
                amount_mad = None

        # Sanitize due_date (YYYY-MM-DD)
        due_date: Optional[str] = None
        raw_date = raw.get("due_date")
        if raw_date and isinstance(raw_date, str):
            date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", raw_date.strip())
            if date_match:
                due_date = date_match.group(0)

        # Source message ID validation: every item must cite a real message
        source_id = raw.get("source_message_id")
        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            logger.warning(f"Dropping item with non-integer source_message_id: {source_id}")
            continue

        # If valid_message_ids is provided, drop any item citing a non-existent message ID
        if valid_message_ids and source_id not in valid_message_ids:
            logger.warning(
                f"Dropping item: source_message_id {source_id} is not in valid_message_ids {valid_message_ids}"
            )
            continue

        confidence_raw = str(raw.get("confidence", "high")).lower().strip()
        confidence = "low" if confidence_raw == "low" else "high"

        item: Item = {
            "id": 0,
            "client_id": client_id,
            "type": item_type,  # type: ignore
            "description": description,
            "owner": owner,      # type: ignore
            "amount_mad": amount_mad,
            "due_date": due_date,
            "source_message_id": source_id,
            "confidence": confidence,  # type: ignore
            "status": "open",
        }
        sanitized.append(item)

    return sanitized


def extract_items(
    client_name: str,
    messages: List[Message],
    existing_items: Optional[List[Item]] = None,
) -> Dict[str, Any]:
    """Extract tasks, promises, deadlines, payments, and questions from a conversation.
    
    Returns {"summary": str, "items": List[Item]}.
    If existing_items is provided, only NEW items are returned.
    Strictly avoids hallucination; casual conversations return empty items list.
    """
    if existing_items is None:
        existing_items = []

    if not messages:
        return {"summary": f"No messages recorded for {client_name}.", "items": []}

    valid_message_ids = {msg.get("id", 0) for msg in messages if msg.get("id") is not None}
    client_id = messages[0].get("client_id", 0) if messages else 0

    # Handle chunking if conversation is longer than 150 messages
    CHUNK_SIZE = 120
    if len(messages) > 150:
        logger.info(f"Chunking conversation of {len(messages)} messages for extraction.")
        all_items: List[Item] = []
        last_summary = ""
        current_existing = list(existing_items)

        for i in range(0, len(messages), CHUNK_SIZE):
            chunk = messages[i : i + CHUNK_SIZE]
            res = extract_items(client_name, chunk, existing_items=current_existing)
            last_summary = res.get("summary", last_summary)
            new_chunk_items = res.get("items", [])
            all_items.extend(new_chunk_items)
            current_existing.extend(new_chunk_items)

        return {"summary": last_summary, "items": all_items}

    # Format inputs
    messages_str = _format_messages_for_prompt(messages)
    existing_str = (
        json.dumps(
            [{"type": it["type"], "description": it["description"], "owner": it["owner"]} for it in existing_items],
            indent=2
        )
        if existing_items
        else "None"
    )

    template = _read_prompt("extract.txt")
    prompt = (
        template.replace("{client_name}", client_name)
        .replace("{existing_items}", existing_str)
        .replace("{messages}", messages_str)
    )

    # First attempt
    summary = ""
    raw_items = []
    parse_success = False

    try:
        raw_text = llm.call_llm(prompt, json=True)
        data = json.loads(raw_text)
        summary = data.get("summary", "")
        raw_items = data.get("items", [])
        parse_success = True
    except Exception as e:
        logger.warning(f"Initial extraction parse failed: {e}. Retrying once with error correction...")
        # Retry once with explicit error instruction
        retry_prompt = (
            f"{prompt}\n\nIMPORTANT: Your previous attempt failed with error: {e}. "
            "Please ensure you return ONLY valid, well-formed JSON matching the specified schema."
        )
        try:
            raw_text = llm.call_llm(retry_prompt, json=True)
            data = json.loads(raw_text)
            summary = data.get("summary", "")
            raw_items = data.get("items", [])
            parse_success = True
        except Exception as retry_err:
            logger.error(f"Retry extraction failed: {retry_err}")
            return {
                "summary": f"Could not analyze conversation for {client_name}.",
                "items": [],
                "error": str(retry_err),
            }

    if not summary:
        summary = f"Discussion history with {client_name}."

    items = _validate_and_sanitize_items(raw_items, valid_message_ids=valid_message_ids, client_id=client_id)
    return {"summary": summary, "items": items}


def make_brief(client_name: str, items: List[Item], recent_messages: List[Message]) -> str:
    """Generate an executive 5-line preparation brief for an upcoming call with a client.
    
    5 lines max: status, my promises, client's promises, money owed, next step.
    """
    last_msgs = recent_messages[-20:] if len(recent_messages) > 20 else recent_messages
    messages_str = _format_messages_for_prompt(last_msgs)

    # Format simplified items representation
    items_summary = [
        {
            "type": it.get("type"),
            "description": it.get("description"),
            "owner": it.get("owner"),
            "amount_mad": it.get("amount_mad"),
            "due_date": it.get("due_date"),
            "status": it.get("status"),
        }
        for it in items
    ]
    items_str = json.dumps(items_summary, indent=2) if items_summary else "No tracked items."

    template = _read_prompt("brief.txt")
    prompt = (
        template.replace("{client_name}", client_name)
        .replace("{items}", items_str)
        .replace("{messages}", messages_str)
    )

    try:
        brief_text = llm.call_llm(prompt, json=False)
        # Ensure it is not empty
        if brief_text and len(brief_text.strip()) > 10:
            return brief_text.strip()
    except Exception as e:
        logger.error(f"Failed to generate brief via LLM: {e}")

    # Deterministic fallback brief if LLM fails
    money_owed = sum(it.get("amount_mad") or 0.0 for it in items if it.get("owner") == "client" and it.get("status") == "open")
    my_tasks = [it.get("description") for it in items if it.get("owner") == "me" and it.get("status") == "open"]
    client_tasks = [it.get("description") for it in items if it.get("owner") == "client" and it.get("status") == "open"]

    return (
        f"1. Status: Ongoing collaboration with {client_name} ({len(items)} items tracked).\n"
        f"2. My promises: {'; '.join(my_tasks[:2]) if my_tasks else 'None outstanding.'}\n"
        f"3. Client's promises: {'; '.join(client_tasks[:2]) if client_tasks else 'None outstanding.'}\n"
        f"4. Money owed: {money_owed:,.2f} MAD.\n"
        f"5. Suggested next step: Follow up to confirm timeline and outstanding items."
    )


def draft_reply(brief: str, goal: str) -> Dict[str, str]:
    """Draft follow-up messages based on a client brief.
    
    goal: payment_reminder | confirm_delivery | quote_followup | thank_you.
    Returns {"whatsapp": str, "email": str}.
    """
    valid_goals = {"payment_reminder", "confirm_delivery", "quote_followup", "thank_you"}
    if goal not in valid_goals:
        goal = "quote_followup"

    template = _read_prompt("draft.txt")
    prompt = template.replace("{goal}", goal).replace("{brief}", brief)

    try:
        raw_text = llm.call_llm(prompt, json=True)
        data = json.loads(raw_text)
        wa = data.get("whatsapp", "").strip()
        email = data.get("email", "").strip()
        if wa and email:
            return {"whatsapp": wa, "email": email}
    except Exception as e:
        logger.warning(f"LLM draft_reply failed ({e}), using reliable fallback draft.")

    # High quality fallback drafts in English
    fallbacks = {
        "payment_reminder": {
            "whatsapp": "Hi! Just a friendly follow-up regarding the outstanding payment so we can keep everything on schedule. Thank you!",
            "email": "Dear Client,\n\nI hope this email finds you well. This is a gentle reminder regarding the pending balance for our recent order. Please let us know once transferred so we can proceed with the next steps.\n\nBest regards,\nManagement",
        },
        "confirm_delivery": {
            "whatsapp": "Hello! Confirming that your order is on track as agreed. We will deliver it on schedule. Thank you!",
            "email": "Dear Client,\n\nWe are writing to confirm that the delivery for your order is proceeding according to our agreed schedule. Please let us know if you have any questions.\n\nBest regards,\nManagement",
        },
        "quote_followup": {
            "whatsapp": "Hi! Just checking in to see if you had any questions regarding the quote we discussed. Looking forward to your thoughts!",
            "email": "Dear Client,\n\nI hope you are having a productive week. I am following up on the quotation sent earlier to see if you have any feedback or require further details.\n\nBest regards,\nManagement",
        },
        "thank_you": {
            "whatsapp": "Thank you for your business and trust! It was a pleasure working with you. Have a great day!",
            "email": "Dear Client,\n\nThank you for partnering with us. We truly appreciate your business and look forward to working together again in the future.\n\nBest regards,\nManagement",
        },
    }
    return fallbacks.get(goal, fallbacks["quote_followup"])
