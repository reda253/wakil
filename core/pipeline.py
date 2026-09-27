"""Export and live-message pipelines.  Owner: D3."""
from core import ai


def process_export(path, owner_name, client_name, client_phone=None):
    """unzip -> parse -> transcribe -> save messages (skip dupes) -> extract -> save items. Return client_id."""
    # STUB
    return 1


def process_live_message(client_name, msg_type, content):
    """get/create client -> save message (source="whatsapp") -> transcribe if voice
    -> extract_items(last ~30 messages, existing_items=open items) -> save. Return new items."""
    # STUB
    return ai.extract_items(client_name, [])["items"][:1]
