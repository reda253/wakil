# Wakil: Developer Work Split (No Merge Conflicts)

**The one rule that prevents merge conflicts: every file has exactly ONE owner. You only edit your own files.**
If you need something changed in someone else's file, message the owner. Git can't conflict on files only one person touches.

> Adapt folder names to your existing repo if they differ; what matters is that the ownership table below stays strict.

---

## 1. Ownership table

| Dev | Area | Files you own (and ONLY you edit) |
|-----|------|-----------------------------------|
| **D1** | AI Engine | `core/speech.py` · `core/llm.py` · `core/ai.py` · `prompts/*` |
| **D2** | Brev + WhatsApp Live | `brev/*` · `server/webhook.py` · `server/commands.py` · `server/whatsapp_api.py` |
| **D3** | Data + Export Path | `core/parser.py` · `core/db.py` · `core/pipeline.py` · `pages/1_Import.py` |
| **D4** | App UI + Deploy | `app.py` · `pages/2_Dashboard.py` · `pages/3_Client.py` · `pages/4_Brief_Reply.py` · `ui/components.py` · `.streamlit/*` · `packages.txt` · `requirements.txt` · `.env.example` · `README.md` |
| **Frozen** | Shared contracts | `core/contracts.py`: written once in step 0, then **nobody** edits it without telling the whole team |

**Streamlit pages are separate files on purpose:** D3 and D4 both build UI at the same time without touching the same file.

---

## 2. Step 0: skeleton (ONE person, 10 minutes, before anyone codes)

D4 creates **every file above** with stub content, pushes to `main`, and everyone pulls. After that, nobody creates or deletes shared files.

1. **Create `requirements.txt` complete from the start** so nobody needs to edit it later:
   ```
   streamlit
   sqlalchemy
   psycopg2-binary
   python-dotenv
   requests
   groq
   google-genai
   openai
   fastapi
   uvicorn
   python-multipart
   pydantic
   ```
   (D2's GPU-only packages, faster-whisper and vLLM, go in `brev/requirements-gpu.txt`, owned by D2.)
   Need a new package later? **Message D4**; D4 adds it.

2. **Create `.env.example` complete from the start:**
   ```
   GROQ_API_KEY=
   GEMINI_API_KEY=
   BREV_WHISPER_URL=
   BREV_LLM_URL=
   DATABASE_URL=sqlite:///wakil.db
   WA_TOKEN=
   WA_PHONE_NUMBER_ID=
   WA_VERIFY_TOKEN=
   ```
   Check `.gitignore` contains `.env`, `*.db`, `__pycache__/`, `uploads/`, `cache/`.

3. **Create `core/contracts.py`** (the shared shapes, frozen):
   ```python
   from typing import TypedDict, Literal, Optional

   class Message(TypedDict):
       id: int
       client_id: int
       timestamp: str            # "2026-09-27T14:32"
       sender: Literal["owner", "client"]
       type: Literal["text", "voice"]
       content: str              # text, or audio file path
       transcript: Optional[str]
       source: Literal["export", "whatsapp"]

   class Item(TypedDict):
       id: int
       client_id: int
       type: Literal["task", "promise", "payment", "deadline", "question"]
       description: str
       owner: Literal["me", "client"]
       amount_mad: Optional[float]
       due_date: Optional[str]   # "YYYY-MM-DD"
       source_message_id: int
       confidence: Literal["high", "low"]
       status: Literal["open", "done"]
   ```

4. **Every function below exists as a stub** returning fake example data, so all 4 devs can build and run the app immediately.

---

## 3. Function contracts (who provides what, who calls what)

| Function | Owner | Called by |
|----------|-------|-----------|
| `speech.transcribe(audio_path) -> {"text", "provider"}` | D1 | D3 (pipeline) |
| `llm.call_llm(prompt, json=True) -> str` | D1 | D1 only |
| `ai.extract_items(client_name, messages, existing_items=[]) -> {"summary", "items"}` | D1 | D3 (pipeline) |
| `ai.make_brief(client_name, items, recent_messages) -> str` | D1 | D2 (bot), D4 (UI) |
| `ai.draft_reply(brief, goal) -> {"whatsapp", "email"}` | D1 | D4 (UI) |
| `parser.parse_export(path, owner_name) -> (client_name, list[Message])` | D3 | D3 (pipeline) |
| `pipeline.process_export(path, owner_name, client_name, client_phone=None) -> client_id` | D3 | D3 (Import page) |
| `pipeline.process_live_message(client_name, msg_type, content) -> list[Item]` | D3 | D2 (bot) |
| `db.get_clients() / get_client(id) / get_or_create_client(name, phone=None)` | D3 | D2, D4 |
| `db.get_items(client_id=None, status="open") -> list[Item]` | D3 | D2, D4 |
| `db.get_messages(client_id, limit=None) -> list[Message]` | D3 | D1, D4 |
| `db.get_message(message_id) -> Message` | D3 | D4 ("View source") |
| `db.set_item_status(item_id, status)` | D3 | D4 |
| `db.get_money_owed() -> list[{"client", "amount_mad"}]` | D3 | D2, D4 |

**Changing a signature?** Tell everyone who calls it **before** pushing. Adding a new function in your own file is always fine.

---

## 4. Tasks per developer

### D1: AI Engine (`core/speech.py`, `core/llm.py`, `core/ai.py`, `prompts/`)

1. **`llm.call_llm()`** with fallback chain: Brev vLLM (`BREV_LLM_URL`, skipped if empty, via the `openai` client with `base_url`) → Gemini → Groq. Timeout on each; log which provider answered.
2. **`speech.transcribe()`**:
   - `convert_audio()`: ffmpeg `.opus` → 16 kHz mono `.wav`.
   - Chain: Brev Whisper (`BREV_WHISPER_URL`) → Groq Whisper large-v3 → Gemini audio. `language="en"` everywhere.
   - Cache transcripts by file hash in `cache/`.
3. **`ai.extract_items()`**:
   - Messages formatted as numbered lines `[12] 2026-09-27 14:32 client: ...`.
   - Prompt in `prompts/extract.txt`: only explicit facts; "tomorrow / next Friday / end of month" → real dates from message timestamps; amounts → number; unclear → `confidence: "low"`; every item cites `source_message_id`; if `existing_items` given, return only NEW items.
   - Validate JSON (fields, types, `source_message_id` exists); retry once with the error; else return empty with an `error` key.
   - Chunk chats longer than ~150 messages.
4. **`ai.make_brief()`**: 5 lines max (status, my promises, client's promises, money owed, next step). Prompt in `prompts/brief.txt`.
5. **`ai.draft_reply()`**: goals `payment_reminder`, `confirm_delivery`, `quote_followup`, `thank_you`. Returns a short WhatsApp message + a formal email. Prompt in `prompts/draft.txt`.

**Done when:** a small script (keep it in `prompts/` or run it in your terminal) extracts correct items from 2 sample chats, and a small-talk chat returns zero items.

---

### D2: Brev + WhatsApp Live (`brev/*`, `server/*`)

**Brev (only D2 starts/stops GPU instances):**
1. `brev/whisper_server.py`: FastAPI `POST /transcribe` running faster-whisper large-v3, `language="en"`.
2. `brev/start_vllm.sh`: serves an ~8B open instruct model with vLLM (OpenAI-compatible).
3. `brev/requirements-gpu.txt`: GPU packages.
4. Get a public HTTPS URL for both; give `BREV_WHISPER_URL` and `BREV_LLM_URL` to D1 privately (not in group chats).
5. Stop the instance when idle; keep it running from submission to 20:00 for judging.

**WhatsApp live channel:**
1. `server/whatsapp_api.py`: `send_text(to, body)`, `get_media_url(media_id)`, `download_media(url, path)`.
2. `server/commands.py`: pure functions, easy to test without WhatsApp:
   - `client <name>` → sets the active client (in a small dict or DB call) → "Now filing messages under Ahmed."
   - `brief <name>` → `ai.make_brief(...)`
   - `tasks` → `db.get_items(status="open")` formatted by due date
   - `help` → command list
   - anything else → `pipeline.process_live_message(active_client, "text", body)`
   - no active client → "Which client is this about? Send: client <name>"
3. `server/webhook.py`: FastAPI app.
   - `GET /webhook`: Meta verification (`hub.verify_token` check, return `hub.challenge`).
   - `POST /webhook`: **return 200 immediately**, process in a background task.
   - Voice note → download → `pipeline.process_live_message(active_client, "voice", audio_path)` → reply "✅ Noted for Ahmed: …".
   - Any error → friendly reply, never silence.
4. Run it on the Brev instance or a laptop + ngrok; register the callback URL in Meta; subscribe to the `messages` field.

**Done when:** forwarding an English voice note to the test number returns a correct "✅ Noted for …" reply, and the item appears in the app (shared database).

---

### D3: Data + Export Path (`core/parser.py`, `core/db.py`, `core/pipeline.py`, `pages/1_Import.py`)

1. **`db.py`**: SQLAlchemy using `DATABASE_URL` (Guepard Postgres URL, or `sqlite:///wakil.db` fallback). Tables: `clients(id, name, phone)`, `messages(...)`, `items(...)` matching `contracts.py`. Create tables on first run. Implement every `db.*` function in section 3.
   - Guepard Cloud: **20-minute timebox**, then SQLite. The WhatsApp server and the deployed app can only share data through a hosted database, so try it.
2. **`parser.py`**:
   - Android `dd/mm/yyyy, hh:mm - Name: text` and iPhone `[dd/mm/yyyy, hh:mm:ss] Name: text`.
   - Multi-line messages (a line without a date belongs to the previous message).
   - Voice-note lines linked to the `.opus` files extracted from the `.zip`.
   - `sender` = `"owner"` if the name matches `owner_name`, else `"client"`.
   - Mask phone numbers in text.
3. **`pipeline.py`**:
   - `process_export()`: unzip → parse → transcribe voice notes → save messages (skip duplicates: same client + timestamp + content) → extract → save items → return `client_id`.
   - `process_live_message()`: get/create client → save message (`source="whatsapp"`) → transcribe if voice → `extract_items(..., existing_items=open items)` on the last ~30 messages → save and return new items.
4. **`pages/1_Import.py`**: upload `.zip`/`.txt`, owner name, client name, optional client phone, consent checkbox ("I have informed my clients"), progress bar (parsing → transcribing X/Y → extracting), then a link to the client's page.

**Done when:** importing a real exported chat from an Android and an iPhone shows correct items in the database.

---

### D4: App UI + Deploy (`app.py`, pages 2–4, `ui/components.py`, config files)

1. **Step 0 skeleton** (section 2), pushed first.
2. **`app.py`**: title, short description, navigation. Nothing else, so nobody else needs to touch it.
3. **`ui/components.py`**: reusable pieces: `item_card(item)` (colored tag by type, orange if low confidence, "📱 via WhatsApp" badge if the source message came from WhatsApp, "View source" expander showing `db.get_message()`, done checkbox calling `db.set_item_status()`), `money_badge(amount)`, `empty_state(text)`.
4. **`pages/2_Dashboard.py`**: all open items sorted by due date; overdue in red; "Who owes me money" box from `db.get_money_owed()` with total in MAD.
5. **`pages/3_Client.py`**: client picker, summary, items (via `item_card`), message history with transcripts.
6. **`pages/4_Brief_Reply.py`**: client picker → "Prepare my call" → `ai.make_brief()`; goal buttons → `ai.draft_reply()`; show both drafts with a copy button; the note "Wakil never sends messages on your behalf."
7. **Deploy** (Streamlit Community Cloud or Hugging Face Spaces): secrets set; `packages.txt` with `ffmpeg`; test the public link on a phone and in a private window.
8. **`README.md`**: what it is, how to run locally, stack, known limitations.

**Done when:** all pages work on real data at the public link.

---

## 5. Git workflow

**Everyone works directly on `main`, only in their own files:**
```bash
git pull --rebase              # before starting, and before every push
# ... edit ONLY your files ...
git add core/ai.py prompts/    # add your files by name, never "git add ."
git commit -m "ai: extraction with JSON validation"
git pull --rebase
git push
```

Rules:
- **Never `git add .` or `git add -A`**: it can commit someone else's files, `.env`, the database or audio files by accident.
- Commit and push **small and often** (every 20–30 minutes), so others always have your latest functions.
- **Run the app before pushing**; never push code that breaks the import of your module.
- If `git pull --rebase` ever conflicts, **stop and tell the file's owner**. Don't resolve a conflict in someone else's file.

---

## 6. Milestones

| When | Must work |
|------|-----------|
| +15 min | Skeleton with stubs pushed; everyone runs `streamlit run app.py` locally |
| 13:45 | Real transcription (Groq) and extraction; export path saves real items |
| 14:45 | Export path end to end in the UI; WhatsApp bot replies to a forwarded note |
| **15:30** | **Feature freeze**: only bug fixes after this |
| 16:00 | Deployed public link works |
| 17:15 | Submitted |

**If behind, cut in this order (last one first):** Brev LLM → WhatsApp live → brief & draft page → dashboard polish. The export path and extraction quality are never cut.
