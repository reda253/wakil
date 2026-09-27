"""Export and live-message pipelines.  Owner: D3.

process_export()      .zip/.txt -> messages -> transcripts -> items -> database
process_live_message() one forwarded WhatsApp message -> new items only

Two things here that are easy to get wrong and expensive to debug live:

  * The .zip is extracted into a directory unique to this run.  Reusing one path
    leaves the previous chat's PTT-*.opus in place, and the next import then
    resolves its voice notes to the wrong audio.
  * Item.source_message_id must resolve to a real message, or the "view source"
    button is dead.  D1 may cite either the per-chat local_id or the database row
    id, so both are accepted and normalised to local_id on the way in.

Audio is deleted once transcription is done (responsible-AI claim in the
submission).  D1's transcript cache is keyed by file hash and survives.
"""
import os
import shutil
import uuid
import zipfile

from core import ai, db, parser, speech

UPLOAD_ROOT = os.getenv("WAKIL_UPLOADS", "data/uploads")


def _progress(cb, stage, current=None, total=None):
    if cb:
        try:
            cb(stage, current, total)
        except TypeError:
            cb(stage)  # a one-argument callback is still useful


def _extract_zip(zip_path, dest):
    """Unpack and return (txt_path, {filename: absolute_path})."""
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)

    txt_path, txt_size, media = None, -1, {}
    for root, _dirs, files in os.walk(dest):
        for name in files:
            full = os.path.abspath(os.path.join(root, name))
            if name.lower().endswith(".txt"):
                size = os.path.getsize(full)
                # iOS names it _chat.txt, Android "WhatsApp Chat with X.txt";
                # if there are several, the largest is the transcript.
                if size > txt_size:
                    txt_path, txt_size = full, size
            else:
                media[name] = full
    return txt_path, media


def _resolve_source_ids(client_id, items, warnings):
    """Map every item's source_message_id onto a real local_id, dropping the rest."""
    by_local, by_row = db.local_id_map(client_id)
    resolved, dropped = [], 0
    for item in items:
        ref = item.get("source_message_id")
        if ref is None:
            dropped += 1
            continue
        try:
            ref = int(ref)
        except (TypeError, ValueError):
            dropped += 1
            continue
        local = by_local.get(ref, by_row.get(ref))
        if local is None:
            dropped += 1
            continue
        item = dict(item)
        item["source_message_id"] = local
        resolved.append(item)
    if dropped:
        warnings.append(
            f"{dropped} extracted item(s) pointed at a message that is not in the "
            "chat and were discarded.")
    return resolved


def _transcribe_pending(client_id, audio_by_local_id, progress_cb, warnings):
    """Transcribe voice notes that have no transcript yet."""
    pending = [m for m in db.get_messages(client_id)
               if m["type"] == "voice" and not (m["transcript"] or "").strip()]
    if not pending:
        return 0, 0
    failed = 0
    for n, row in enumerate(pending, 1):
        audio = audio_by_local_id.get(row["local_id"])
        if not audio or not os.path.exists(audio):
            failed += 1
            warnings.append(
                f"The audio for message {row['local_id']} is not in the archive.")
            continue
        _progress(progress_cb, "Transcribing", n, len(pending))
        try:
            result = speech.transcribe(audio) or {}
            text = (result.get("text") or "").strip()
            if text:
                db.set_transcript(row["id"], text)
            else:
                failed += 1
        except Exception as exc:  # one bad clip must not fail the whole import
            failed += 1
            warnings.append(
                f"Transcription failed for message {row['local_id']}: {exc}")
    return len(pending), failed


def process_export(path, owner_name, client_name=None, client_phone=None,
                   progress_cb=None):
    """Import one export.  Returns client_id.

    progress_cb(stage, current, total) is called with human-readable stage names.
    """
    warnings = []
    work_dir = None
    client_id = None

    _progress(progress_cb, "Unpacking export")
    txt_path, media_paths = path, {}
    if zipfile.is_zipfile(path):
        os.makedirs(UPLOAD_ROOT, exist_ok=True)
        work_dir = os.path.join(UPLOAD_ROOT, uuid.uuid4().hex[:12])
        try:
            txt_path, media_paths = _extract_zip(path, work_dir)
        finally:
            if txt_path is None:
                shutil.rmtree(work_dir, ignore_errors=True)
        if txt_path is None:
            raise ValueError("No .txt transcript found inside that archive.")
    elif not os.path.exists(path):
        raise FileNotFoundError(path)

    try:
        _progress(progress_cb, "Parsing chat")
        detected, messages = parser.parse_export(
            txt_path, owner_name, media_paths=media_paths, warnings=warnings)
        if not messages:
            warnings.append("No messages were recognised in that file. "
                            "Is it a WhatsApp export?")

        name = (client_name or detected or "Unknown Client").strip()
        client_id = db.get_or_create_client(name, phone=client_phone)

        _progress(progress_cb, "Saving messages")
        # Re-importing the same chat must reuse the local_ids it already has, or the
        # UNIQUE(client_id, local_id) constraint sees brand new rows and the whole
        # conversation is stored twice - which then doubles the money-owed total.
        known = db.existing_message_keys(client_id)
        next_id = db.next_local_id(client_id)
        audio_by_local_id = {}
        for msg in messages:
            key = (msg.get("timestamp"), msg.get("sender"), msg.get("type"),
                   (msg.get("content") or "").strip())
            if key in known:
                local_id = known[key]
            else:
                local_id = next_id
                next_id += 1
                known[key] = local_id  # guards against duplicates inside one file
            msg["local_id"] = local_id
            if msg.get("type") == "voice" and msg.get("audio_path"):
                audio_by_local_id[local_id] = msg["audio_path"]
        db.save_messages(client_id, messages, problems=warnings)

        _transcribe_pending(client_id, audio_by_local_id, progress_cb, warnings)

        _progress(progress_cb, "Extracting items")
        stored = db.get_messages(client_id)
        summary, items = "", []
        try:
            result = ai.extract_items(name, stored) or {}
            summary = result.get("summary") or result.get("client_summary") or ""
            items = result.get("items") or []
        except Exception as exc:
            warnings.append(f"Extraction failed: {exc}")

        if summary:
            db.set_client_summary(client_id, summary)

        items = _resolve_source_ids(client_id, items, warnings)

        _progress(progress_cb, "Saving items")
        # Re-importing the same chat must not double the money-owed total.
        db.delete_open_items(client_id)
        db.save_items(client_id, items)

        return client_id
    finally:
        # Data minimisation: the owner's voice notes do not outlive their transcript.
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        _store_warnings(client_id, warnings)


_WARNINGS = {}


def _store_warnings(client_id, warnings):
    if client_id is not None and warnings:
        _WARNINGS[client_id] = list(warnings)


def get_warnings(client_id):
    """Problems from the last import of this client, for the UI to surface."""
    return list(_WARNINGS.get(client_id, []))


def process_live_message(client_name, msg_type="text", content="",
                         client_phone=None, progress_cb=None):
    """Store one forwarded message and return only the items it introduced.

    No incremental "what's new" prompt: the model is re-run over the whole stored
    thread and the database decides what is new, because a forwarded message
    usually *resolves* an existing open item rather than creating a new one.
    """
    warnings = []
    client_id = db.get_or_create_client(client_name, phone=client_phone)
    local_id = db.next_local_id(client_id)

    row = {
        "local_id": local_id,
        "id": local_id,
        "timestamp": _now(),
        "sender": "client",  # the owner forwards somebody else's message
        "type": "voice" if msg_type == "voice" else "text",
        "content": content,
        "transcript": None,
        "source": "whatsapp",
    }
    db.save_messages(client_id, [row])

    if row["type"] == "voice" and content and os.path.exists(content):
        _progress(progress_cb, "Transcribing", 1, 1)
        try:
            result = speech.transcribe(content) or {}
            text = (result.get("text") or "").strip()
            if text:
                stored = db.get_messages(client_id)
                db.set_transcript(stored[-1]["id"], text)
        except Exception as exc:
            warnings.append(f"Transcription failed: {exc}")
    elif row["type"] == "voice":
        warnings.append("Voice note was not downloaded; only the filename is stored.")

    _progress(progress_cb, "Extracting items")
    stored = db.get_messages(client_id)
    try:
        result = ai.extract_items(client_name, stored) or {}
        items = result.get("items") or []
        summary = result.get("summary") or result.get("client_summary")
    except Exception as exc:
        warnings.append(f"Extraction failed: {exc}")
        items, summary = [], None
    if summary:
        db.set_client_summary(client_id, summary)

    items = _resolve_source_ids(client_id, items, warnings)
    before = {(_key(i)) for i in db.get_items(client_id, status=None)}
    fresh = [i for i in items if _key(i) not in before]
    db.save_items(client_id, fresh)
    _store_warnings(client_id, warnings)
    return fresh


def _key(item):
    return (item.get("type"), item.get("source_message_id"),
            (item.get("description") or "").strip())


def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%dT%H:%M")
