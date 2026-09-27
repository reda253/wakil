# Wakil

Wakil turns a small business owner's WhatsApp chats and voice notes into tasks, deadlines, promises and payments owed. It prepares a brief before each client call and drafts the follow-up message. Wakil never sends anything itself; the owner copies the draft and sends it.

Built for the **GOMYCODE × NVIDIA "Come Build with AI" Hackathon**, September 27, 2026.

## Stack

Streamlit · SQLAlchemy (Guepard Postgres or SQLite) · Groq Whisper / Gemini / NVIDIA Brev (faster-whisper + vLLM) · FastAPI for the WhatsApp webhook · ffmpeg

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # add your keys
streamlit run app.py
```

WhatsApp webhook: `uvicorn server.webhook:app --port 8080`

## Layout

```
app.py, pages/, ui/      Streamlit app
core/                    contracts, parser, db, pipeline, speech, llm, ai
prompts/                 LLM prompts
server/                  WhatsApp webhook and bot commands
brev/                    GPU services on NVIDIA Brev
docs/                    plans and work split
```

## Known limitations

TODO
