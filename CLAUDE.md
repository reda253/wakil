# CLAUDE.md — Wakil

Hackathon project (GOMYCODE × NVIDIA "Come Build with AI", **Sun 2026-09-27**). One-day build.
- Dev split, ownership, contracts, tasks: [docs/wakil_dev_split.md](docs/wakil_dev_split.md) ← **source of truth for structure**
- Product plan, pitch, scoring, timeline: [docs/hackathon_build_plan.md](docs/hackathon_build_plan.md)

## What it is
Wakil (وكيل) = AI agent for small businesses run on WhatsApp. Two input paths:
1. **Export path**: WhatsApp "Export chat" `.zip`/`.txt` (with `.opus` voice notes) → parse → transcribe → extract.
2. **Live path**: WhatsApp Cloud API webhook; owner forwards messages/voice notes to the bot.
Output: tasks, promises, payments, deadlines, questions, **each linked to its source message**; dashboard; "who owes me money"; pre-call brief; draft reply (WhatsApp + formal email).

## Hard rules
- **Every file has exactly ONE owner. Only edit files owned by the dev you're helping.** Need a change elsewhere → tell the user to message that owner. Adding new functions in your own file is fine.
- `core/contracts.py` is **frozen**. Don't change it without the whole team agreeing.
- Changing a function signature → callers must be told first (see contracts table below).
- New package → D4 adds it to `requirements.txt` (GPU packages → `brev/requirements-gpu.txt`, D2).
- Git: work on `main`; `git pull --rebase` before start and before push; **`git add <own files>` by name, never `git add .` / `-A`**; small commits; never resolve conflicts in someone else's file.
- Never commit `.env`, `*.db`, `uploads/`, `cache/`, audio.
- The Streamlit app never sends messages. Drafts only; the owner sends. (The WhatsApp bot only replies to the owner's own commands.)
- No invented facts: extract only what's explicit; unclear → `confidence: "low"`; small-talk chat → zero items; every item cites a real `source_message_id`.
- **Feature freeze 15:30. Submit by 17:15.** Cut order if behind (cut first → last): Brev LLM → WhatsApp live → brief & draft page → dashboard polish. Export path + extraction quality are never cut.

## Ownership
| Dev | Area | Files |
|---|---|---|
| D1 | AI Engine | `core/speech.py` `core/llm.py` `core/ai.py` `prompts/*` |
| D2 | Brev + WhatsApp Live | `brev/*` `server/webhook.py` `server/commands.py` `server/whatsapp_api.py` |
| D3 | Data + Export Path | `core/parser.py` `core/db.py` `core/pipeline.py` `pages/1_Import.py` |
| D4 | App UI + Deploy | `app.py` `pages/2_Dashboard.py` `pages/3_Client.py` `pages/4_Brief_Reply.py` `ui/components.py` `.streamlit/*` `packages.txt` `requirements.txt` `.env.example` `README.md` |
| Frozen | Contracts | `core/contracts.py` |

## Contracts
Shapes in `core/contracts.py`: `Message` (`sender`: `"owner"|"client"`, `source`: `"export"|"whatsapp"`) and `Item` (`owner`: `"me"|"client"`, `status`, `confidence`, `source_message_id`). Note `Message.sender` uses `"owner"` but `Item.owner` uses `"me"`.

| Function | Owner | Called by |
|---|---|---|
| `speech.transcribe(audio_path) -> {"text","provider"}` | D1 | D3 |
| `llm.call_llm(prompt, json=True) -> str` | D1 | D1 |
| `ai.extract_items(client_name, messages, existing_items=[]) -> {"summary","items"}` | D1 | D3 |
| `ai.make_brief(client_name, items, recent_messages) -> str` | D1 | D2, D4 |
| `ai.draft_reply(brief, goal) -> {"whatsapp","email"}` (goal: `payment_reminder`/`confirm_delivery`/`quote_followup`/`thank_you`) | D1 | D4 |
| `parser.parse_export(path, owner_name) -> (client_name, list[Message])` | D3 | D3 |
| `pipeline.process_export(path, owner_name, client_name, client_phone=None) -> client_id` | D3 | D3 |
| `pipeline.process_live_message(client_name, msg_type, content) -> list[Item]` | D3 | D2 |
| `db.get_clients() / get_client(id) / get_or_create_client(name, phone=None)` | D3 | D2, D4 |
| `db.get_items(client_id=None, status="open")`, `db.get_messages(client_id, limit=None)`, `db.get_message(message_id)`, `db.set_item_status(item_id, status)`, `db.get_money_owed() -> [{"client","amount_mad"}]` | D3 | D1, D2, D4 |

Step 0 state: every function is a **stub** (marked `# STUB`) returning fake data so the app runs end to end. Replace stubs in place; keep signatures. Import modules as `from core import db, ai, ...`.

## Stack & key decisions
- Python 3.10+, Streamlit multipage (`pages/`), SQLAlchemy on `DATABASE_URL` (Guepard Postgres, 20-min timebox, else `sqlite:///wakil.db`). Hosted DB is what lets the webhook server and deployed app share data.
- STT chain: Brev faster-whisper (`BREV_WHISPER_URL`) → Groq Whisper large-v3 → Gemini audio. `language="en"`. ffmpeg `.opus` → 16 kHz mono `.wav`. Cache by file hash in `cache/`.
- LLM chain in `llm.call_llm`: Brev vLLM (`BREV_LLM_URL`, OpenAI client `base_url`, skipped if empty) → Gemini → Groq. Timeouts; log provider.
- Extraction: numbered lines `[12] 2026-09-27 14:32 client: ...`; validate JSON (fields, types, source id exists); retry once with error; else empty + `error` key; chunk >~150 messages.
- Prompt files contain literal JSON braces: fill with `.replace("{x}", ...)`, **not** `str.format`.
- Webhook: `GET /webhook` Meta verify; `POST /webhook` returns 200 immediately, processes in background; errors → friendly reply.
- Deploy: Streamlit Community Cloud / HF Spaces; `packages.txt` → ffmpeg; secrets set there.
- Brev: WSL Ubuntu-22.04 on the lead's laptop has `brev` CLI installed (`brev login`, `brev ls`). Only D2 starts/stops GPU instances; stop when idle.

## Commands
```bash
pip install -r requirements.txt
streamlit run app.py
uvicorn server.webhook:app --port 8080
```
