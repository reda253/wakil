"""WhatsApp Cloud API helpers (WA_TOKEN, WA_PHONE_NUMBER_ID).  Owner: D2."""
import os
import requests

GRAPH_URL = "https://graph.facebook.com/v19.0"


def send_text(to: str, body: str) -> bool:
    """Send a text message via WhatsApp Cloud API."""
    token = os.getenv("WA_TOKEN")
    phone_id = os.getenv("WA_PHONE_NUMBER_ID")
    if not token or not phone_id:
        print(f"[send_text -> {to}] (Simulated - no WA credentials): {body}")
        return False

    url = f"{GRAPH_URL}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[send_text error] {e}")
        return False


def get_media_url(media_id: str) -> str:
    """Retrieve temporary download URL for a media ID from Meta."""
    token = os.getenv("WA_TOKEN")
    if not token or not media_id:
        return ""

    url = f"{GRAPH_URL}/{media_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json().get("url", "")
    except Exception as e:
        print(f"[get_media_url error] {e}")
        return ""


def download_media(url: str, path: str) -> str:
    """Download binary media from Meta URL to local file path."""
    token = os.getenv("WA_TOKEN")
    if not token or not url:
        return path

    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f"[download_media error] {e}")
        return path

