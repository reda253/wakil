"""WhatsApp webhook.  Owner: D2.  Run: uvicorn server.webhook:app --port 8080"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()


@app.get("/webhook")
def verify(request: Request):
    p = request.query_params
    if p.get("hub.verify_token") == os.getenv("WA_VERIFY_TOKEN"):
        return PlainTextResponse(p.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/webhook")
async def receive(request: Request):
    # STUB: return 200 immediately, process in a background task
    return {"status": "ok"}
