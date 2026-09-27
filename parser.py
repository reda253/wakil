"""WhatsApp chat export -> list[Message].  Owner: P4.

Formats to support:
  Android: 27/09/2026, 14:32 - Ahmed: message
  iPhone:  [27/09/2026, 14:32:05] Ahmed: message
Voice notes: "PTT-20260927-WA0003.opus (file attached)" (text varies by phone language).
Lines without a date belong to the previous message. Mask phone numbers.
"""


def parse_export(file_path, my_name=None):
    """Return (client_name, list[Message]).

    Message = {"id": int, "timestamp": "YYYY-MM-DDTHH:MM", "sender": "me"|"client",
               "type": "text"|"voice", "content": str, "transcript": str|None}
    """
    # STUB: replace with real parser
    return "Ahmed", [
        {"id": 1, "timestamp": "2026-09-20T10:05", "sender": "client", "type": "text",
         "content": "Salam, bghit cuisine kamla, ch7al taman?", "transcript": None},
        {"id": 2, "timestamp": "2026-09-20T10:12", "sender": "me", "type": "text",
         "content": "15000 dh, khassni 50% avance w nsalik f 15 jours.", "transcript": None},
        {"id": 3, "timestamp": "2026-09-21T18:40", "sender": "client", "type": "voice",
         "content": "PTT-20260921-WA0001.opus",
         "transcript": "Wakha, ghadi nsiftlik l'avance nhar l'jem3a."},
    ]
