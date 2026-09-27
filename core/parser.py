"""WhatsApp export -> messages.  Owner: D3.

Both real export layouts, one code path:

    Android  27/09/2026, 14:32 - Ahmed: Salam
    Android  27/09/2026, 2:32 PM - Ahmed: Salam      (12h locale, narrow no-break space)
    iPhone   [27/09/2026, 14:32:05] Ahmed: Salam

Voice notes carry the filename, not the audio:

    Android  PTT-20260927-WA0003.opus (file attached)     EN
    Android  PTT-20260927-WA0003.opus (fichier joint)     FR
    Android  PTT-20260927-WA0003.opus (ملف مرفق)          AR
    iPhone   <attached: 00000042-AUDIO-2026-09-27-14-23-01.opus>

Traps that silently break a naive parser, all handled here:
  * U+200E, the left-to-right mark iOS injects before attachment markers
  * CRLF endings and a possible UTF-8 BOM
  * the format is detected once, from the first header, and applied to the whole file
  * "export without media" replaces the filename with a single space: warn, never guess
  * system lines (encryption notice, deleted message, missed call) carry no "Name:" and
    are never turned into messages
  * phone numbers are masked, but 4-5 digit amounts and quantities are left alone

Message = {"id", "client_id", "timestamp", "sender": "me"|"client",
           "type": "text"|"voice", "content", "transcript", "source",
           "audio_path"}
`id` is 1-based per chat; pipeline.process_export shifts it past anything already
stored.  `audio_path` is a transient absolute path and is never persisted, so the
row can outlive the extracted audio.
"""
import os
import re

_AUDIO_EXT = r"(?:opus|ogg|oga|m4a|mp3|wav|aac|amr|m4r)"
_ANY_EXT = r"(?:" + _AUDIO_EXT + r"|mp4|3gp|jpe?g|png|webp|pdf|docx?|xlsx?|xls)"

_FILENAME_RE = re.compile(r"([^\s<>()\[\]]+\." + _ANY_EXT + r")\b", re.I)
_IOS_ATTACH_RE = re.compile(r"<[^<>\n]{0,40}:\s*([^\n<>]{1,120}?)\s*>")
_ANDROID_ATTACH_RE = re.compile(
    r"([^\s<>()\[\]]+\." + _ANY_EXT + r")\s*\(\s*([^)\n]{1,40}?)\s*\)", re.I)

# WhatsApp's own media naming is the most reliable attachment signal we have.
_WA_MEDIA_RE = re.compile(r"^(?:PTT|IMG|VID|AUD|DOC|STK)-|AUDIO-", re.I)
# The parenthesised word after an Android filename varies by phone locale.
_ATTACH_WORDS = {
    "file attached", "fichier joint", "archivo adjunto", "arquivo anexado",
    "anexo", "datei anhang", "angefugt", "allegato", "bijlage", "bilaga",
    "liitetty tiedosto", "attached", "file", "مرفق", "ملف مرفق",
}

_DATE = r"(\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4})"
_TIME = r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s?m\.?)?)"
# re.I matters: English and French exports write "2:32 PM" in upper case, and some
# locales drop the space ("2:32PM").  Without it those lines are not recognised at all.
_ANDROID_RE = re.compile(r"^\s*" + _DATE + r",\s*" + _TIME + r"\s*-\s*(.*)$", re.I)
_IOS_RE = re.compile(r"^\s*\[\s*" + _DATE + r",\s*" + _TIME + r"\s*\]\s*(.*)$", re.I)

# After the timestamp, anything that is not "Name: ..." is a WhatsApp system event.
_SYSTEM_NAME_RE = re.compile(
    r"^(?:you\b|your\b|this message|messages and calls|security code|missed|"
    r"group\b|\u2026|\.\.\.)", re.I)
_MEDIA_OMITTED = {
    "media omitted", "image omitted", "video omitted", "audio omitted",
    "sticker omitted", "document omitted", "image/video omitted",
}

# Conservative on purpose: a 4-5 digit amount must survive, so nothing here matches
# a bare run of 9+ digits unless it is prefixed or is a Moroccan mobile number.
_PHONE_RES = (
    re.compile(r"(?<![\w+])\+\d(?:[\s.\-()]*\d){7,14}(?!\d)"),
    re.compile(r"(?<!\d)00(?:212|221|1|2)\d(?:[\s.\-]*\d){6,12}(?!\d)"),
    re.compile(r"(?<!\d)21[02]\d(?:[\s.\-]*\d){7,11}(?!\d)"),
    re.compile(r"(?<!\d)0[5-7](?:[\s.\-]?\d{2}){4}(?!\d)"),
)

PHONE_PLACEHOLDER = "[PHONE]"


def _clean(line):
    """Strip the invisible characters WhatsApp sprinkles through exports."""
    return (line.replace("\u200e", "")
                .replace("\u202f", " ")
                .replace("\u00a0", " ")
                .replace("\ufeff", ""))


def _norm_name(name):
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def mask_phone(text):
    """Replace phone numbers with [PHONE].  Amounts and dates are left intact."""
    if not text:
        return text
    for rx in _PHONE_RES:
        text = rx.sub(PHONE_PLACEHOLDER, text)
    return text


def _detect_dayfirst(lines):
    """dd/mm vs mm/dd.  Unambiguous when a component exceeds 12; else dd/mm."""
    dayfirst_votes = monthfirst_votes = 0
    for line in lines:
        m = re.search(_DATE, line)
        if not m:
            continue
        parts = re.split(r"[/.\-]", m.group(1))
        if len(parts) != 3 or len(parts[0]) == 4 or len(parts[2]) != 4:
            continue
        try:
            a, b = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if a > 12:
            dayfirst_votes += 1
        elif b > 12:
            monthfirst_votes += 1
    return monthfirst_votes <= dayfirst_votes


def _parse_date(text, dayfirst):
    parts = re.split(r"[/\-.]", text.strip())
    if len(parts) != 3:
        return None
    try:
        a, b, c = (int(p) for p in parts)
    except ValueError:
        return None

    if len(parts[0]) == 4:                        # 2026/09/27
        y, mo, d = a, b, c
    elif len(parts[2]) == 4:                      # 27/09/2026 or 09/27/2026
        y, mo, d = (c, b, a) if dayfirst else (c, a, b)
    elif len(parts[2]) == 2:                      # 27/09/26
        y, mo, d = (2000 + c, b, a) if dayfirst else (2000 + c, a, b)
    else:
        return None
    if not (1 <= mo <= 12 and 1 <= d <= 31 and 1970 <= y <= 2100):
        return None
    return y, mo, d


def normalize_timestamp(d_str, t_str, dayfirst=True):
    """-> "YYYY-MM-DDTHH:MM", the shape core/contracts.py documents."""
    parsed = _parse_date(d_str, dayfirst)
    if not parsed:
        return None
    y, mo, d = parsed

    t = t_str.lower().strip()
    pm, am = "pm" in t, "am" in t
    t = re.sub(r"\s*(?:a|p)\.?\s?m?\.?$", "", t).strip()
    parts = t.split(":")
    try:
        h = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None
    if pm and h < 12:
        h += 12
    elif am and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{minute:02d}"


def _attachment(body):
    """Return the media filename a message body references, or None."""
    m = _IOS_ATTACH_RE.search(body)
    if m:
        found = _FILENAME_RE.search(m.group(1))
        if found:
            return found.group(1)
    m = _ANDROID_ATTACH_RE.search(body)
    if m:
        filename, paren = m.group(1), m.group(2).strip().lower()
        if (paren in _ATTACH_WORDS
                or _WA_MEDIA_RE.search(filename)
                or (len(paren) <= 25 and not re.search(r"[.!?]", paren))):
            return filename
    return None


def _is_audio(filename):
    return bool(re.search(r"\.(?:" + _AUDIO_EXT + r")$", filename or "", re.I))


def _media_omitted(body):
    """WhatsApp's marker when the user exported *without* media."""
    return body.strip().lower() in _MEDIA_OMITTED


def _client_name_from_filename(txt_path):
    """'WhatsApp Chat with Ahmed.txt' -> 'Ahmed'.  iOS '_chat.txt' -> None."""
    stem = os.path.basename(txt_path)
    if stem.lower() in ("_chat.txt", "chat.txt"):
        return None
    m = re.match(r"whatsapp chat with (.+?)\.txt$", stem, re.I)
    return m.group(1).strip() if m else None


def _build(current, media_paths):
    """Turn an accumulated header + body lines into a Message dict."""
    body = "\n".join(current["_body"]).strip()
    filename = _attachment(body)

    msg_type, content, audio_path = "text", body, None
    if filename and _is_audio(filename):
        msg_type = "voice"
        audio_path = (media_paths.get(filename)
                      or media_paths.get(os.path.basename(filename)))
        # Persist the basename, never the absolute path: the extracted audio is
        # deleted once the pipeline finishes, and a dead path in the row is worse
        # than no path at all.
        content = os.path.basename(filename)
    elif filename:
        content = f"[{os.path.basename(filename)}]"

    content = mask_phone(content)
    return {
        "id": current["id"],
        "client_id": 0,
        "timestamp": current["timestamp"],
        "sender": current["sender"],
        "type": msg_type,
        "content": content,
        "transcript": current.get("transcript"),
        "source": "export",
        "audio_path": audio_path,
    }, filename


def _header_senders(lines):
    """Distinct sender names, in the order they first appear.  One cheap pre-pass."""
    seen, mode = [], None
    for line in lines:
        if not line.strip():
            continue
        header, found = None, None
        if mode in (None, "android"):
            m = _ANDROID_RE.match(line)
            if m:
                header, found = m, "android"
        if header is None and mode in (None, "iphone"):
            m = _IOS_RE.match(line)
            if m:
                header, found = m, "iphone"
        if header is None:
            continue
        mode = found
        name, sep, _body = header.groups()[2].partition(":")
        if not sep or _SYSTEM_NAME_RE.match(name.strip()):
            continue
        if name.strip() not in seen:
            seen.append(name.strip())
    return seen


def _resolve_owner(owner_name, client_name, lines, warnings):
    """Decide which sender is "me".  Returns (owner_key, senders).

    Getting this backwards is not cosmetic: it decides who owes whom, so every
    fallback is chosen to be the most reliable signal available, in this order:

      1. the owner name the user typed - always trusted, with a loose match on the
         first word so a full name still matches a chat that shows only a first name
      2. the export filename, which names the *client* ("WhatsApp Chat with
         Ahmed Benali"), so any other sender is the owner.  Only used if a sender
         really does match the filename, otherwise it is ignored
      3. the first speaker in the file, which is a guess: in a chat the client
         often greets first.  The caller warns about this.
    """
    senders = _header_senders(lines)
    keys = {_norm_name(s) for s in senders}

    given = _norm_name(owner_name)
    if given:
        if given in keys:
            return given, senders
        # "Youssef El Mansouri" typed, but the chat only ever shows "Youssef".
        first = given.split()[0]
        loose = {s for s in keys
                 if s.split()[0] == first or first.startswith(s) or s.startswith(first)}
        if len(loose) == 1:
            return loose.pop(), senders
        if len(loose) > 1:
            warnings.append(
                f"'{owner_name}' matches more than one person in the chat "
                f"({', '.join(sorted(loose))}), so no message was attributed to you. "
                "Use the name exactly as it appears in the chat.")
            return "", senders
        warnings.append(
            f"'{owner_name}' does not appear in this chat. The people in it are "
            f"{', '.join(senders) or '(none found)'}, so the split between you and "
            "your client below is a guess - re-import with the exact name to fix it.")
    else:
        warnings.append(
            "No owner name given, so the split between you and your client is a "
            f"guess ('{senders[0] if senders else '?'}' was treated as you). "
            "Check the dashboard and re-import with your name if it is wrong.")

    from_file = _norm_name(client_name) if client_name else ""
    if from_file and from_file in keys:
        # Every sender who is not the client named in the filename is the owner.
        return next(s for s in keys if s != from_file), senders

    return (_norm_name(senders[0]) if senders else ""), senders


def parse_export(file_path, owner_name=None, media_paths=None, warnings=None):
    """Return (client_name, list[Message]).

    media_paths maps a media filename to its absolute path on disk (pipeline builds
    it from the .zip).  A voice note whose file is missing from media_paths still
    parses as voice, and the pipeline reports it instead of dropping it silently.

    warnings is an optional list that collects human-readable problems.
    """
    media_paths = media_paths or {}
    if warnings is None:
        warnings = []

    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [_clean(l) for l in fh.read().splitlines()]

    dayfirst = _detect_dayfirst(lines)
    client_name = _client_name_from_filename(file_path)
    owner_key, senders = _resolve_owner(owner_name, client_name, lines, warnings)

    messages = []
    current = None
    mode = None
    media_without_file = 0
    missing_audio = 0

    def flush():
        nonlocal media_without_file, missing_audio
        if current is None:
            return
        body = "\n".join(current["_body"]).strip()
        msg, filename = _build(current, media_paths)
        if msg["type"] == "voice" and msg["audio_path"] is None:
            missing_audio += 1
        elif not filename and _media_omitted(body):
            media_without_file += 1
        messages.append(msg)

    for line in lines:
        if not line.strip():
            continue  # blank line: separator between logical messages

        header, found_mode = None, None
        if mode in (None, "android"):
            m = _ANDROID_RE.match(line)
            if m:
                header, found_mode = m, "android"
        if header is None and mode in (None, "iphone"):
            m = _IOS_RE.match(line)
            if m:
                header, found_mode = m, "iphone"

        if header is None:
            if current is not None:
                current["_body"].append(line)   # continuation of the same message
            # else: preamble (encryption notice) or a system line -> dropped
            continue

        if current is not None:
            flush()

        mode = found_mode  # detected once, then held for the whole chat
        d_str, t_str, rest = header.groups()
        timestamp = normalize_timestamp(d_str, t_str, dayfirst)

        sender_raw, sep, body = rest.partition(":")
        name = sender_raw.strip()
        is_system = (not sep) or _SYSTEM_NAME_RE.match(name)
        if timestamp is None or is_system:
            current = None
            continue

        sender = "me" if _norm_name(name) == owner_key else "client"
        if sender == "client" and not client_name:
            client_name = name
        current = {
            "id": len(messages) + 1,
            "timestamp": timestamp,
            "sender": sender,
            "type": "text",
            "transcript": None,
            "_body": [body.strip()],
        }

    if current is not None:
        flush()

    if media_without_file:
        warnings.append(
            f"{media_without_file} message(s) had media excluded from the export. "
            "Re-export with 'Attach media' to transcribe them.")
    if missing_audio:
        warnings.append(
            f"{missing_audio} voice note(s) are referenced but are not in the archive.")

    return client_name or "Unknown Client", messages
