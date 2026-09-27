"""Shared shapes. FROZEN: nobody edits this without telling the whole team."""
from typing import TypedDict, Literal, Optional


class Message(TypedDict):
    id: int
    client_id: int
    timestamp: str            # "2026-09-27T14:32"
    sender: Literal["owner", "client"]
    type: Literal["text", "voice"]
    content: str              # text, or audio file path
    transcript: Optional[str]
    source: Literal["export", "whatsapp"]


class Item(TypedDict):
    id: int
    client_id: int
    type: Literal["task", "promise", "payment", "deadline", "question"]
    description: str
    owner: Literal["me", "client"]
    amount_mad: Optional[float]
    due_date: Optional[str]   # "YYYY-MM-DD"
    source_message_id: int
    confidence: Literal["high", "low"]
    status: Literal["open", "done"]
