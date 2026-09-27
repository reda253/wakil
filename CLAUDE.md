# CLAUDE.md — Wakil

Hackathon project (GOMYCODE × NVIDIA "Come Build with AI", **Sun 2026-09-27, Morocco**). One-day build.
Full plan: [docs/hackathon_build_plan.md](docs/hackathon_build_plan.md). Roles/timeline: [docs/team_work_split.md](docs/team_work_split.md). Read those when a question is about scope, timing, scoring or pitch.

## What it is
Wakil (وكيل) = AI agent for Moroccan small businesses run on WhatsApp. Input: WhatsApp "Export chat" `.txt`/`.zip` (with `.opus` voice notes in Darija/French/Arabic). Output: tasks, promises, payments, deadlines, questions — **each linked to its source message** — plus a dashboard, a "who owes me money" view, a pre-call brief, and a draft reply (WhatsApp Darija-Latin or French + formal email).

## Hard rules (don't break these)
- **App never sends messages or makes calls.** Drafts only; user copies them.
- **No invented facts.** Extract only explicit content. Ambiguous → `confidence: "low"` (shown orange). Small-talk chat must yield **zero** items.
- **Every item has a valid `source_message_id`** that exists in the input. Drop items that don't.
- **Never commit API keys.** `.env` / `.streamlit/secrets.toml` are gitignored.
- **Feature freeze 15:30. Submit by 17:15.** After freeze: bug fixes, deploy, video only. Prefer cutting scope over adding.
- Out of scope: real WhatsApp Business API, auto-sending, Gmail/calendar integrations.
- API path first; NVIDIA Brev only if approved and API path already works (stop at 14:45 if not working).

## Stack
Python 3.10+ (file `parser.py` shadows the old stdlib `parser` on 3.9), Streamlit multipage, SQLite, ffmpeg.
- STT: Groq Whisper large-v3 → fallback Gemini audio. Cache transcripts by filename.
- LLM: Gemini Flash (JSON mode) → fallback Groq-hosted model / NVIDIA Build, all behind `ai.call_llm()`.
- Model names come from env vars (`.env.example`); verify names in consoles, don't hardcode.
- Deploy: Streamlit Community Cloud (`packages.txt` → ffmpeg; keys in Secrets).

## Layout and owners
Each person owns their files to avoid merge conflicts. Only P3 edits `app.py` and `pages/`.
| File | Owner | Purpose |
|---|---|---|
| `app.py`, `pages/1_Import.py` `2_Dashboard.py` `3_Client.py` `4_Brief_and_Reply.py` | P3 | UI |
| `db.py` | P3 | SQLite: clients, messages, items |
| `parser.py` | P4 | export → messages |
| `speech.py` | P1 | audio → text |
| `ai.py`, `prompts/*.txt` | P2 | extraction, brief, reply |
| `tests/evaluate.py`, `tests/data/<scenario>/` | P4 | accuracy scoring |

## Contracts (all modules code against these)
```python
Message = {"id": int, "timestamp": "2026-09-27T14:32", "sender": "me"|"client",
           "type": "text"|"voice", "content": str, "transcript": str|None}   # content = text or audio path
Item = {"type": "task"|"promise"|"payment"|"deadline"|"question", "description": str,
        "owner": "me"|"client", "amount_mad": float|None, "due_date": "YYYY-MM-DD"|None,
        "source_message_id": int, "confidence": "high"|"low"}

parser.parse_export(file_path, my_name=None) -> (client_name, list[Message])
speech.transcribe(audio_path) -> {"text", "language", "provider"}
ai.extract_items(client_name, messages) -> {"client_summary", "items"}
ai.make_brief(client_name, items, recent_messages) -> str        # 5 lines max
ai.draft_reply(brief, goal, language) -> {"whatsapp", "email"}
```
Modules start as **stubs returning hard-coded data** (marked `# STUB`) so the UI works end to end from minute one. Replace stubs in place; keep signatures.

DB note: `messages.local_id` = parser's `Message["id"]`; `items.source_message_id` refers to it (per client). Use `db.get_source_message(client_id, local_id)` for "view source".

## Implementation notes
- Parser: Android `27/09/2026, 14:32 - Name: text`, iPhone `[27/09/2026, 14:32:05] Name: text`; lines without a date continue the previous message; voice notes look like `PTT-...opus (file attached)` (wording depends on phone language); mask phone numbers; user picks which sender is "me".
- LLM input format: numbered lines `[12] 2026-09-27 14:32 client: ...` so the model can cite ids.
- Validate LLM JSON; on failure retry once with the error, then return empty result + error flag.
- Relative dates ("ghda", "next Friday") → absolute from message timestamp. Amounts ("1500 dh", "alf w khmsmya", "1.5k") → number.
- Chunk long chats (~150 messages), merge, dedupe.
- Prompt files contain literal JSON braces: fill placeholders with `.replace("{client_name}", ...)`, **not** `str.format`.
- Show a small "fallback used" indicator when a fallback provider answered.
- UI text in simple French (Darija where natural).

## Commands
```bash
pip install -r requirements.txt
streamlit run app.py
python -m tests.evaluate      # prints correct / missed / invented per test chat
```

## Testing
5 scenarios in `tests/data/` (carpenter, event planner, supplier w/ unpaid invoice, voice-only heavy Darija, small talk). Each has `expected.json` written by hand. Goal metric for pitch: "X/Y items correct, 0 invented, N s per chat". Use synthetic/consented data only.
