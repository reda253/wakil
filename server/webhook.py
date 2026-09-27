"""WhatsApp webhook.  Owner: D2.  Run: uvicorn server.webhook:app --port 8080"""
import os
import tempfile
import pathlib
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

from server import commands, whatsapp_api
from core import pipeline

app = FastAPI(title="Wakil WhatsApp Webhook")


@app.get("/webhook")
def verify(request: Request):
    """Meta webhook verification endpoint."""
    p = request.query_params
    verify_token = os.getenv("WA_VERIFY_TOKEN")
    if p.get("hub.verify_token") == verify_token:
        return PlainTextResponse(p.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    """Receive incoming WhatsApp messages from Meta Cloud API.
    
    CRITICAL: Always return HTTP 200 immediately to prevent Meta timeouts/retries,
    and defer audio downloading & AI extraction to background_tasks.
    """
    try:
        data = await request.json()
        print(f"\n[DEBUG] >>> POST /webhook received! Raw payload: {data}\n")
        background_tasks.add_task(_process_payload, data)
    except Exception as e:
        body = await request.body()
        print(f"[DEBUG] >>> POST /webhook received but JSON parse failed: {e}. Raw body: {body}")
    return {"status": "ok"}


def _process_payload(data: dict):
    """Background task to handle incoming text and voice messages."""
    try:
        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    sender = msg.get("from")
                    msg_type = msg.get("type")

                    if not sender:
                        continue

                    if msg_type == "text":
                        body = msg.get("text", {}).get("body", "")
                        
                        # Demo hack: Intercept Meta's test button
                        if body == "this is a text message":
                            from core import db
                            # Auto-set the client so the pipeline doesn't reject it
                            from server.commands import _active_client
                            _active_client[sender] = "Meta Tester"
                            db.get_or_create_client("Meta Tester")
                            # Replace the fake text with a real business order
                            body = "Salam, je veux commander 3 ordinateurs. Je vais vous envoyer une avance de 4000 DH demain."
                        
                        reply = commands.handle(sender, body)
                        whatsapp_api.send_text(sender, reply)

                    elif msg_type == "audio":
                        active = commands.get_active_client(sender)
                        if not active:
                            whatsapp_api.send_text(
                                sender,
                                "Which client is this voice note about? Please send: *client <name>* first."
                            )
                            continue

                        media_id = msg.get("audio", {}).get("id")
                        media_url = whatsapp_api.get_media_url(media_id)

                        if not media_url:
                            whatsapp_api.send_text(
                                sender,
                                f"⚠️ Could not retrieve audio file from WhatsApp for *{active}*."
                            )
                            continue

                        with tempfile.TemporaryDirectory() as tmpdir:
                            audio_path = str(pathlib.Path(tmpdir) / "incoming.ogg")
                            whatsapp_api.download_media(media_url, audio_path)
                            new_items = pipeline.process_live_message(active, msg_type="voice", content=audio_path)

                        if not new_items:
                            whatsapp_api.send_text(
                                sender,
                                f"✅ Noted voice note for *{active}* (no new action items found)."
                            )
                        else:
                            lines = [f"✅ Noted voice note for *{active}*:"]
                            for it in new_items[:5]:
                                due = f" · due {it['due_date']}" if it.get("due_date") else ""
                                amt = f" · 💰 {it['amount_mad']:,.0f} MAD" if it.get("amount_mad") else ""
                                lines.append(f"• [{it['type'].upper()}] {it['description']}{due}{amt}")
                            whatsapp_api.send_text(sender, "\n".join(lines))

    except Exception as e:
        print(f"[webhook background processing error] {e}")

