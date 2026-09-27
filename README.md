# Wakil · وكيل

Wakil turns a small business owner's WhatsApp chats and Darija voice notes into a clear list of tasks, deadlines, promises and payments owed. It also prepares a brief before each client call and drafts the follow-up message.

Built for the **GOMYCODE × NVIDIA "Come Build with AI" Hackathon**, September 27, 2026, Morocco.

## How it works

```
WhatsApp export (.txt/.zip) → parser → transcription (Groq Whisper → Gemini)
  → extraction (Gemini Flash → fallback LLM, validated JSON) → SQLite → Streamlit UI
```

Every extracted item links back to the message it came from. Items the model is unsure about are flagged for the owner to check. Wakil never sends a message on its own; the owner copies the draft and sends it.

## Run locally

Needs Python 3.10+ and ffmpeg.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # then add your API keys
streamlit run app.py
```

Evaluation on the test chats:

```bash
python -m tests.evaluate
```

## Deploy (Streamlit Community Cloud)

Main file `app.py`. Add the keys from `.env.example` under **Secrets**. `packages.txt` installs ffmpeg.

## Responsible AI

- Demo data is synthetic or comes from people who agreed to share it.
- Phone numbers are masked. Audio is deleted after transcription, and data stays in a local database.
- Wakil drafts messages but never sends anything; the owner reviews and sends.
- Darija transcription is not perfect, so items with low confidence are flagged.
- Chat text and audio go to Groq and Google APIs. A production version would need a data agreement or a local model.

## Team

| Role | Owns |
|---|---|
| P1 Speech & Infra | `speech.py`, `requirements.txt`, `.env.example` |
| P2 AI & Prompts | `ai.py`, `prompts/` |
| P3 App & Deploy | `app.py`, `pages/`, `db.py` |
| P4 Parser & Testing | `parser.py`, `tests/` |
| P5 Lead & Pitch | submission, video, project sheet |
