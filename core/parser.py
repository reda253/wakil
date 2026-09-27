"""WhatsApp export -> messages.  Owner: D3.

Android `dd/mm/yyyy, hh:mm - Name: text`, iPhone `[dd/mm/yyyy, hh:mm:ss] Name: text`.
Multi-line messages, voice notes linked to .opus files, sender "owner" if name == owner_name, mask phones.
"""


def parse_export(path, owner_name):
    """Return (client_name, list[Message])."""
    # STUB
    return "Ahmed", [
        {"id": 1, "client_id": 0, "timestamp": "2026-09-20T10:05", "sender": "client", "type": "text",
         "content": "Hi, I want a full kitchen, how much?", "transcript": None, "source": "export"},
        {"id": 2, "client_id": 0, "timestamp": "2026-09-20T10:12", "sender": "owner", "type": "text",
         "content": "15,000 MAD, 50% deposit, delivery in 15 days.", "transcript": None, "source": "export"},
        {"id": 3, "client_id": 0, "timestamp": "2026-09-21T18:40", "sender": "client", "type": "voice",
         "content": "PTT-20260921-WA0001.opus", "transcript": "Okay, I'll send you the deposit on Friday.",
         "source": "export"},
    ]
