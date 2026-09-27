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

## Pages

- **Dashboard**: money owed, open orders, promises and items that need a check (click "Details" on a card for the breakdown), who owes you money, a priority board, and the pre-call brief.
- **Orders**: what you promised to deliver, who is waiting for it, and how urgent it is (Urgent = late, High = today or tomorrow, Normal = within 7 days, Low = later or no date).
- **Clients & history**: one client's items and full message history.
- **Brief & reply**: a 5-line summary before a call, then a WhatsApp message and an email to copy.
- **Import chat**: upload a WhatsApp export.

## Tests

```bash
python -m pytest tests/ui -q
```

UI tests use an in-memory fake of `core.db` and `core.ai`, so they run without API keys or a database. Set `WAKIL_TODAY=2026-09-27` to pin "today" for demos.

## Deploy

| Layer | Where | Notes |
|---|---|---|
| App | Streamlit Community Cloud | Deploys from GitHub `main`; every push redeploys. |
| Database | Guepard Cloud Postgres 16 | One endpoint; demo data in schema `public`, pytest in schema `wakil_test`. Reset with a Guepard snapshot. |
| Speech | Brev GPU instance `wakil-whisper` (faster-whisper large-v3, port 8000) | Groq Whisper is the automatic fallback. |
| LLM | Gemini, then Groq | `BREV_LLM_URL` empty: no model is served on Brev. |

### Streamlit Community Cloud

1. share.streamlit.io -> Create app -> repo `reda253/wakil`, branch `main`, main file `app.py`. Advanced settings: Python 3.12.
2. Advanced settings -> Secrets (TOML, values in quotes; root-level keys become environment variables):

   ```toml
   DATABASE_URL = "postgresql://guepard:<password>@<host>:<port>/postgres?sslmode=require"
   GROQ_API_KEY = "..."
   GEMINI_API_KEY = "..."
   BREV_WHISPER_URL = "https://<brev-host>"
   WHISPER_TOKEN = "..."   # only once the Whisper server checks it
   BREV_LLM_URL = ""
   ```

   Never set `WAKIL_DB` (forces SQLite) or `WAKIL_TODAY` (freezes the date) in the cloud.
3. `packages.txt` installs ffmpeg for voice notes.
4. Check: the logs show `[db] backend=postgres ...` with the password masked, and data survives "Reboot app".

Connection strings and keys live only in local `.env` (gitignored), Streamlit secrets, and the Brev instance. Never in the repo or a public channel.

## Known limitations

- **WhatsApp API Publishing:** The webhook and Meta Graph API integration are 100% complete and tested in our codebase. However, receiving live messages from arbitrary users requires a published Meta App, which requires business verification (takes days). For the hackathon, we demo this live pipeline using Meta's Test Webhook tool, which fully simulates the production flow. Moving to production only requires clicking "Publish" in the Meta dashboard.
- Darija transcription is imperfect with strong regional accents and noisy audio; such items are marked "Needs check".
- Orders are derived from the tasks, promises and deadlines you owe clients; their urgency comes from the due date only.
- The dashboard only knows what was said in the chats; payments made outside WhatsApp count as open until you tick them done.
- Chat text and audio are sent to third-party AI providers (Groq, Google, NVIDIA); production would need a data agreement or a local model.
- Wakil never sends messages: "Open in WhatsApp" only pre-fills the text.
