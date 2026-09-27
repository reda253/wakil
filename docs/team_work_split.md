# Team Work Split: WhatsApp Business Agent (Wakil)
**Hackathon: Sunday, September 27, 2026 · all times in Tunis time (= Moroccan time right now)**

---

## ⚠️ Read first: the 6th person

The official rules allow **teams of up to 5 people**. Someone who is not registered cannot officially be part of the team, and the jury evaluates *what the registered team builds*. Before Sunday, **ask the organizers** (email or the official channel) whether an unregistered person may help.
- If they say **yes** → use the 6-person split (section 3).
- If they say **no, or you don't get an answer** → use the 5-person split. The 6th person can still help **tonight** with test data (recording voice notes, writing sample conversations), which is preparation, not building.

The 5-person plan is complete on its own. The 6th role is designed as an add-on, so nothing breaks if that person doesn't come.

---

## 1. Roles at a glance

### 5-person team
| # | Role | One-line mission |
|---|------|------------------|
| **P1** | Speech & Infrastructure | Voice notes → text, reliably, with fallbacks (and Brev if approved) |
| **P2** | AI Extraction & Prompts | Text → structured tasks, brief and draft replies, as valid JSON |
| **P3** | App & Deployment | The Streamlit app, database and public link |
| **P4** | Data, Parser & Testing | WhatsApp export parser, test conversations, accuracy scores |
| **P5** | Team Lead, Product & Pitch | Rules, timekeeping, mentor, video, submission |

### 6-person team (adds P6)
| # | Role | One-line mission |
|---|------|------------------|
| **P6** | Design & Demo Production | UI polish, logo, demo storyline, video recording and editing |

With P6, **P5 hands over** the video production and UI polish and focuses on coordination, pitch, submission forms and jury prep.

---

## 2. Shared contracts: agree on these at 10:00 (15 minutes, everyone)

Everyone codes against the same shapes, so people can work in parallel without waiting for each other.

### Repo structure (each person owns their files → no merge conflicts)
```
wakil/
├── app.py              # P3  Streamlit entry point
├── pages/              # P3  (P6 styles them)
├── db.py               # P3  SQLite functions
├── parser.py           # P4  WhatsApp export → messages
├── speech.py           # P1  audio → text
├── ai.py               # P2  extraction, brief, draft reply
├── prompts/            # P2  prompt text files
├── tests/data/         # P4  test conversations + expected results
├── tests/evaluate.py   # P4  scoring script
├── .env.example        # P1  names of API keys (never commit real keys)
└── requirements.txt    # P1
```

### Data shapes
```python
Message = {
  "id": int, "timestamp": "2026-09-27T14:32", "sender": "me" | "client",
  "type": "text" | "voice", "content": str,          # text, or audio file path
  "transcript": str | None
}

Item = {
  "type": "task" | "promise" | "payment" | "deadline" | "question",
  "description": str, "owner": "me" | "client",
  "amount_mad": float | None, "due_date": "YYYY-MM-DD" | None,
  "source_message_id": int, "confidence": "high" | "low"
}
```

### Function signatures
```python
parser.parse_export(file_path) -> (client_name, list[Message])         # P4
speech.transcribe(audio_path) -> {"text", "language", "provider"}      # P1
ai.extract_items(client_name, messages) -> {"client_summary", "items"} # P2
ai.make_brief(client_name, items, recent_messages) -> str              # P2
ai.draft_reply(brief, goal, language) -> {"whatsapp", "email"}         # P2
db.save_client / db.save_messages / db.save_items / db.get_* ...       # P3
```

**Rule:** until a real function works, each owner provides a **fake version** that returns hard-coded example data (a "stub"). P3 builds the UI on the stubs from minute one.

### Git rules
- One repo, `main` branch. Pull before you push. Commit small and often with clear messages.
- Never commit API keys: use `.env` (listed in `.gitignore`).
- Only P3 edits `app.py` and `pages/`; others ask P3.

### Sync points (5 minutes each, standing up)
**11:30 · 13:00 (lunch) · 14:45 · 15:30 (freeze) · 16:30**
Each person says: *done / doing next / blocked by*.

---

## 3. Detailed walkthrough per role

---

### P1: Speech & Infrastructure

**Mission:** every voice note becomes text, fast, with a working fallback. The demo must never fail because of transcription.

**Tonight (preparation only, no product code)**
- Create or check API keys: Groq and Google AI Studio. Write down the exact current model names.
- Test 3–4 real Darija voice notes in the Groq and Gemini web consoles. Note which transcribes Darija better.
- Install Python, ffmpeg and a code editor; check that ffmpeg runs from the terminal.
- If the Brev request was approved: read the Brev quick-start and know how to launch an instance.

**09:00–10:00**
- Create the GitHub repo with the structure above, `.gitignore`, `.env.example`, `requirements.txt`. Invite everyone.
- Make sure each teammate can run an empty Streamlit app on their laptop.

**10:00–11:30: speech module, API path first**
1. Write `convert_audio(path)`: ffmpeg converts `.opus` to `.mp3` or `.wav`.
2. Write `transcribe_groq(path)` using Whisper large-v3 on Groq.
3. Write `transcribe_gemini(path)` as the fallback.
4. Write `transcribe(path)`: try Groq → on error, try Gemini → return `{"text", "language", "provider"}`.
5. Add a **cache**: save each transcript in a JSON file keyed by the audio filename; never transcribe the same file twice.
- ✅ **Done at 11:30:** `transcribe()` works on 3 of P4's voice notes, fallback tested by disabling the Groq key.

**11:45–13:00: robustness**
- Handle errors: empty audio, very long notes (split files over ~10 minutes), network timeouts (retry once).
- Add timing logs (seconds per note) → P4 uses them for the "speed" part of the testing score.
- Help P4 connect the parser to `transcribe()` so voice notes in an export get transcribed automatically.

**13:45–15:30: Brev (only if approved AND the API path works)**
- Launch the GPU instance; install faster-whisper; expose a small endpoint (`/transcribe`).
- Optionally serve an open LLM with vLLM (it exposes an OpenAI-compatible API, so P2 can switch with just a URL change).
- Add `transcribe_brev()` as the **first** option in the chain, with Groq and Gemini behind it.
- Run the same voice notes through Brev and Groq; give P4 the comparison.
- ⛔ If Brev isn't working by **14:45**, stop and stay on the API path. Don't let it eat the afternoon.
- *No Brev?* Spend this time helping P2 with fallback providers and P3 with deployment.

**15:30–16:30**
- Help P3 deploy: set secrets (API keys) on the hosting platform, check ffmpeg is available there (add it to `packages.txt` on Streamlit Cloud).
- Test the deployed app end to end with a voice-note export.

**16:30–17:15**
- Give P5 the exact list of tools and models for the AI declaration (names, why chosen, fallback chain).
- Stay available for last-minute bugs.

---

### P2: AI Extraction & Prompts

**Mission:** turn conversations into reliable, source-linked JSON; generate the brief and draft replies. This is the heart of the "AI quality" score (20 points).

**Tonight**
- Try the extraction prompt from the build plan in Google AI Studio on one sample conversation. Note what goes wrong (invented items, wrong dates, bad JSON). Don't write app code.

**09:00–10:00**
- Write the stub versions of `extract_items`, `make_brief`, `draft_reply` returning fixed example data, so P3 can start the UI.

**10:00–11:30: extraction v1**
1. Put the prompt in `prompts/extract.txt`.
2. Format messages for the model as numbered lines: `[12] 2026-09-27 14:32 client: ...` so the model can cite `source_message_id`.
3. Call Gemini in JSON mode; parse the result.
4. Validate: required fields present, types correct, `source_message_id` exists in the input. Drop invalid items.
5. On invalid JSON: retry once, including the error in the prompt; then return an empty result with an error flag.
- ✅ **Done at 11:30:** real extraction on 2 of P4's test chats, valid JSON every time.

**11:45–13:00: quality**
- Relative dates ("ghda", "next Friday", "had l'week-end") → absolute dates using the message timestamp.
- Amounts in dirhams written in many ways ("1500 dh", "alf w khmsmya", "1.5k") → a number.
- Low confidence instead of guessing; test on P4's "small talk" chat → must return **zero** items.
- Long chats: split into chunks of ~150 messages, merge results, remove duplicates.

**13:45–15:30: brief and draft reply**
1. `make_brief`: 5 lines max: status, my promises, client's promises, money owed, next step.
2. `draft_reply`: goals as buttons ("payment reminder", "confirm delivery date", "quote follow-up"); output a short WhatsApp message (Darija in Latin script, or French) + a formal email.
3. Add the fallback provider (Groq-hosted open model, NVIDIA Build, or P1's Brev vLLM endpoint) behind one `call_llm()` function.
- ✅ **Done at 15:30:** all three functions work on every test chat, with fallback.

**15:30–16:30**
- Fix the failures P4 found. Tune prompts only; no new features.
- Write 3–4 lines for P5: why Gemini, why the fallback, what the AI does that rules can't.

**16:30–17:15**
- Stand by for bugs; review the AI tools declaration for accuracy.

---

### P3: App & Deployment

**Mission:** a clean, simple app anyone can understand in 10 seconds, live at a public link.

**Tonight**
- Sketch the 4 screens on paper (Import, Dashboard, Client page, Brief & Reply). Create a Streamlit Community Cloud or Hugging Face account.

**09:00–10:00**
- Set up the empty Streamlit app with navigation between the 4 pages.

**10:00–11:30: database + pages on stubs**
1. `db.py`: create the 3 tables (clients, messages, items) and save/get functions.
2. **Import page:** file upload (.txt / .zip) + client name + "Analyze" button with a progress bar (parsing → transcribing X/Y → extracting).
3. **Client page:** summary, list of items with colored tags (task / promise / payment / deadline), orange for low confidence.
- ✅ **Done at 11:30:** full flow works using the stubs.

**11:45–13:00: connect real modules**
- Replace stubs with P4's parser, P1's `transcribe`, P2's `extract_items` as they become ready.
- **"View source" button** on each item → shows the original message or transcript. This is the key trust feature for the demo.
- Mark items as done (checkbox saved in the DB).

**13:45–15:30: dashboard + brief page**
1. **Dashboard:** all open items across clients sorted by due date; overdue in red; a **"Who owes me money"** box with totals in MAD.
2. **Brief & Reply page:** pick a client → "Prepare my call" → brief; goal buttons → draft reply with a **Copy** button. Show clearly: "Wakil never sends messages for you."
3. A small consent notice on the Import page (see responsible AI in the build plan).
- ✅ **Done at 15:30:** everything works with real modules; **feature freeze**.

**15:30–16:30: deployment**
- Deploy; add API keys as secrets; add `packages.txt` with `ffmpeg`.
- Test the public link on a phone and in a private browser window.
- Preload 2–3 demo clients so the app never looks empty.

**16:30–17:15**
- Give P5 (or P6) the final link; be on call while the video is recorded.

---

### P4: Data, Parser & Testing

**Mission:** realistic test data, a parser that never breaks, and **real accuracy numbers** for the 15-point testing score.

**Tonight (test data is preparation, not product code; confirm with the mentor at 11:30)**
- Write the 5 test scenarios (carpenter, event planner, supplier with unpaid invoice, heavy-Darija voice notes only, small talk with no business).
- Have two teammates **act them out on WhatsApp** with real voice notes, then export the chats (one from Android, one from iPhone).
- For each chat, write the **expected items by hand** in `expected.json`.

**09:00–10:00**
- Put the test data in `tests/data/` and share it with the team.

**10:00–11:30: parser**
1. Parse Android format `dd/mm/yyyy, hh:mm - Name: text` and iPhone format `[dd/mm/yyyy, hh:mm:ss] Name: text`.
2. Handle multi-line messages (a line without a date belongs to the previous message).
3. Detect voice-note attachments and link them to the audio files in the .zip.
4. Map senders to `"me"` or `"client"` (ask the user which name is theirs).
5. Mask phone numbers in message text.
- ✅ **Done at 11:30:** both export formats parse correctly into `Message` lists.

**11:45–13:00: evaluation script**
- `evaluate.py`: runs the pipeline on each test chat, compares with `expected.json`, prints: correct items, missed items, **invented items**, average time per chat.
- Give P2 a clear list of failures after each run.

**13:45–15:30: test loop**
- Rerun the evaluation after each P2 prompt change; keep a table of results over time.
- Test edge cases: empty chat, chat with only images, a 1,000-message chat, voice notes in French only.
- Report bugs to the owner (P1/P2/P3) with the exact file that caused them.

**15:30–16:30**
- Final evaluation run → the score table for the video and the submission, e.g., *"41/46 items correct, 0 invented, 12 s per chat."*
- Give P5 3 honest "known limitations" (e.g., strong regional accents, very noisy audio).

**16:30–17:15**
- Double-check the submission package with P5 against the checklist.

---

### P5: Team Lead, Product & Pitch

**Mission:** keep the team on time, make sure nothing required is missing, and tell the story that wins. **You don't code**, so you have time to think.

**Tonight**
- Lead the brainstorm; get the team's agreement on the idea and roles.
- Ask the organizers about the 6th person.
- Confirm the team name and leader email (they must match the confirmation form exactly).
- Write a first version of the one-sentence pitch and the user story ("Youssef, carpenter in Tangier…").

**08:30–10:00**
- Join all official channels; watch the opening and note every rule and deliverable.
- **09:45–10:00: confirm attendance before 10:00.** Set an alarm.
- Run the 10:00 contracts meeting (section 2), maximum 15 minutes.

**10:15–11:30**
- Watch the NVIDIA talk; note anything useful (NVIDIA Build, model choices) and pass it to P1/P2.
- Draft the project sheet: name, one-sentence pitch, team members, tools, next step.

**11:30–11:45: mentor check**
- Pitch in 30 seconds. Ask: (1) Is our "why not ChatGPT" answer convincing? (2) Is pre-made test data OK? (3) Any tip on what the jury values most?

**11:45–15:30**
- Run each sync point and **cut scope** whenever someone is late. You own the 15:30 freeze.
- Write the AI tools declaration with inputs from P1 and P2: tools, why chosen, access constraints, what the AI does, fallback.
- Write the responsible-AI paragraph (consent, masked data, audio deletion, human in control).
- Listen to the **13:45 submission brief** and update the checklist.
- Choose the main prize in the dropdown and the partner prizes to tick (Guepard, Yassir, possibly Kredete, EY, Thunders), with one sentence each.
- *(5-person team)* Write the 90-second video script and plan the recording.

**15:30–16:30**
- *(5-person team)* Rehearse the demo twice with P3, timing it.
- Prepare answers to likely jury questions (see the build plan).

**16:30–17:15**
- *(5-person team)* Record and edit the 90-second video with P3; add subtitles.
- **Submit by 17:15 at the latest.** Screenshot the confirmation.

**17:30–19:45**
- Prepare a 2–3 minute live demo in case you're in Morocco's top 3; decide who speaks and who clicks.

---

### P6: Design & Demo Production (only if the 6th person is allowed and present)

**Mission:** make the product look trustworthy and the video unforgettable, so P5 can focus on coordination and the pitch.

**Tonight**
- Pick a name, simple logo and 2 brand colors; gather a clean icon set.
- Watch 2–3 winning hackathon demo videos to borrow their structure.

**09:00–11:30**
- Mock up the 4 screens (Figma or paper) with P3; agree on layout and wording.
- Write all UI text in simple French (with Darija where natural): buttons, empty states, error messages.

**11:45–15:30**
- Apply styling in Streamlit with P3 (theme colors, logo, spacing, clear badges).
- Write the video script with P5 and storyboard it shot by shot.
- Prepare the video's intro and outro cards and the subtitle file.

**15:30–16:30**
- Record practice takes of the screen demo; fix anything that looks confusing on screen.

**16:30–17:00**
- Record the final video (screen + voice), edit to **90 seconds max**, add subtitles, upload with a link that works without login.
- Hand the link to P5 by **17:00**.

---

## 4. If the team is smaller on the day

| Missing person | Who covers |
|----------------|-----------|
| P6 | P5 takes back video and design (the 5-person plan) |
| P1 | P2 uses the API path only (Groq + Gemini); drop Brev |
| P4 | P2 writes the parser; P5 runs the evaluation script |
| P3 | P1 builds the app; keep the UI to 2 pages (Import + Client/Brief) |
| P5 | P4 takes timekeeping and submission; P3 records the video |

---

## 5. The three rules that decide the day

1. **API path first, Brev second.** Nothing fancy until the basic demo works end to end.
2. **Feature freeze at 15:30.** After that, only bug fixes, deployment and the video.
3. **Submit by 17:15.** A good project submitted on time beats a great project submitted at 17:31.
