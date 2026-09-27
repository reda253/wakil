# Build Plan: AI Agent for WhatsApp-Run Small Businesses
**GOMYCODE × NVIDIA "Come Build with AI" Hackathon · Sunday, September 27, 2026 · Morocco**

---

## 0. The one-sentence pitch

> **Wakil** (وكيل, "agent") turns a small business owner's messy WhatsApp chats and Darija voice notes into a clear list of tasks, deadlines, promises and payments owed, then prepares a brief before each client call and drafts the follow-up message for them.

*(The name is a suggestion; pick something short your team likes.)*

**Target user:** a Moroccan small business owner or freelancer who runs the business on WhatsApp: a carpenter (menuisier), event planner, tailor, supplier, contractor, small agency. They receive dozens of voice notes a day in Darija mixed with French, and they forget promises, lose track of quotes and forget who still owes them money.

**Answer to "Why not just use ChatGPT or Gemini?"** (memorize this for the jury)
1. It works on **WhatsApp chat exports and Darija voice notes**, which is how Moroccan business actually runs. General assistants and Copilot-style tools are built around email and Outlook.
2. It **remembers each client over time** and keeps a structured record (tasks, prices, deadlines, payments), instead of a one-off chat answer.
3. It **outputs actions**, not just summaries: a to-do list, reminders, a pre-call brief and a ready-to-send reply.
4. **Every extracted item links back to the exact source message**, so the owner can verify it. No invented facts.

---

## 1. Scope: what we build and what we don't

### MVP (must work live by 15:30)
| # | Feature | What the user sees |
|---|---------|--------------------|
| 1 | **Import** | Upload a WhatsApp chat export (`.txt` or `.zip` with voice notes) for one client |
| 2 | **Transcribe** | Voice notes are turned into text (Darija / French / Arabic) |
| 3 | **Extract** | A structured list: tasks, promises (who promised what), prices and amounts, deadlines, open questions, each with a link to the source message |
| 4 | **Dashboard** | All tasks and reminders across clients, sorted by deadline, with a "who owes me money" view |
| 5 | **Client brief** | "Before calling Ahmed": a 5-line summary of where things stand |
| 6 | **Draft reply** | A follow-up WhatsApp message (Darija or French) or a formal email, which the user copies and sends **themselves** |

### Nice-to-have (only if the MVP is done and tested)
- Ask a question across all clients: *"Which clients are waiting for a quote?"*
- Export reminders to a calendar file (`.ics`)
- Read the brief aloud (text-to-speech) for owners who prefer listening

### Explicitly out of scope (say so in the submission as "next steps")
- Connecting to the real WhatsApp Business API (it needs Meta business verification, which is impossible in one day)
- Automatically sending messages or making calls (the human always confirms)
- Gmail, calendar or task-manager integrations

**Why the chat export approach:** WhatsApp has a built-in "Export chat" feature that produces a text file plus the voice note audio files. This gives us real data with **zero integration work**, so all our time goes into the AI, which is what gets scored.

---

## 2. Architecture

```
[WhatsApp "Export chat" .zip/.txt]
            │
            ▼
   1. Parser (Python)  ──► messages: {timestamp, sender, text | audio_file}
            │
            ▼
   2. Transcription    ──► Groq Whisper (primary) / Gemini audio (fallback)
            │                cache every transcript (never transcribe twice)
            ▼
   3. Extraction LLM   ──► Gemini Flash (primary) / Groq LLM or NVIDIA Build (fallback)
            │                strict JSON output, validated, retried once on failure
            ▼
   4. Storage          ──► SQLite (clients, messages, items)
            │
            ▼
   5. UI (Streamlit)   ──► Import · Dashboard · Client page · Brief · Draft reply
```

### Tech stack (all free tiers)
| Layer | Choice | Why |
|-------|--------|-----|
| UI + app | **Streamlit** (Python) | Fastest way to build a working, clean UI in hours; one language for the whole team |
| Speech-to-text | **Groq API, Whisper large-v3** | Very fast, free tier, multilingual |
| Fallback STT | **Gemini API** (accepts audio directly) | If Groq is down or Darija quality is poor on a clip |
| Extraction and drafting | **Gemini Flash** (Google AI Studio free tier) | Good at Arabic/French/Darija, reliable JSON mode |
| Fallback LLM | A Groq-hosted open model, or a model from **NVIDIA Build** | Mentioning NVIDIA Build as a fallback is a nice touch for the NVIDIA judges |
| Audio conversion | **ffmpeg** | WhatsApp voice notes are `.opus`; convert to `.mp3`/`.wav` if an API rejects them |
| Storage | **SQLite** | No setup, one file |
| Deployment | **Streamlit Community Cloud** or **Hugging Face Spaces** | Free public link for the submission |

> ⚠️ Model names and free-tier limits change. Check the exact current model names in Google AI Studio and the Groq console **tonight**, not on Sunday.

If your team is much stronger in JavaScript, swap Streamlit for Next.js, but only if everyone is comfortable with it. Don't learn a new framework on Sunday.

---

## 3. Data model (SQLite)

```
clients   (id, name, phone_masked, created_at)
messages  (id, client_id, timestamp, sender, type[text|voice], content, transcript, audio_file)
items     (id, client_id, type[task|promise|payment|deadline|question],
           description, owner[me|client], amount_mad, due_date,
           status[open|done], source_message_id, confidence[high|low])
```

`source_message_id` is the key to our reliability story: every item points to the message it came from.

---

## 4. The AI pieces

### 4.1 Parsing WhatsApp exports
The export format differs between Android and iPhone, and between phone languages:
- Android: `27/09/2026, 14:32 - Ahmed: message`
- iPhone: `[27/09/2026, 14:32:05] Ahmed: message`
- Voice notes appear as a filename such as `PTT-20260927-WA0003.opus (file attached)` (the exact text depends on the phone's language)

Write a parser that handles both formats and detects audio attachments. **Test it on exports from at least two different phones** (one Android, one iPhone if possible).

### 4.2 Extraction prompt (starting draft, refine on Sunday)
```
You are an assistant for a Moroccan small business owner.
You receive a WhatsApp conversation between the owner ("me") and a client.
Messages may be in Darija, French, Arabic, or a mix.

Extract ONLY what is explicitly stated. Never guess or invent.
Return valid JSON only, no other text, following this schema:

{
  "client_summary": "2-3 sentences, in French",
  "items": [
    {
      "type": "task | promise | payment | deadline | question",
      "description": "short, in French",
      "owner": "me | client",
      "amount_mad": number or null,
      "due_date": "YYYY-MM-DD" or null,
      "source_message_id": number,
      "confidence": "high | low"
    }
  ]
}

Rules:
- If a date is relative ("ghda", "next Friday"), convert it using the message timestamp.
- If something is ambiguous, set confidence to "low" instead of guessing.
- source_message_id must be the id of the message the item comes from.
```

### 4.3 Brief prompt
Input: the client's items + the last 20 messages. Output: 5 lines max, in the user's preferred language: where things stand, what I promised, what the client promised, money owed, and the suggested next step.

### 4.4 Draft reply prompt
Input: the brief + the goal the user chooses from buttons ("remind about payment", "confirm delivery date", "send quote follow-up"). Output: a short, polite WhatsApp message in Darija (Latin script) or French, plus a formal email version. The user copies it; **the app never sends anything**.

### 4.5 Reliability measures (15 points on testing and reliability; show them in the demo)
- **JSON validation** with a schema check; on failure, retry once with the error message, then show a friendly error.
- **Source links**: each item has a "view source" button showing the original message or transcript.
- **Low-confidence flag**: items marked `low` are shown in orange, "please verify."
- **Transcript cache**: never re-transcribe the same audio (saves time and quota).
- **Fallback chain**: Groq → Gemini for audio; Gemini → second provider for text. Show a small "fallback used" indicator.
- **Chunking**: split long chats into chunks (for example, 150 messages each) to stay within limits and keep latency acceptable.

---

## 5. Test set (build it before 15:30, show the results in the video)

Create **5 realistic test conversations** covering different trades, with real Darija voice notes recorded by team members:

| # | Scenario | What it tests |
|---|----------|---------------|
| 1 | Carpenter + client ordering a kitchen: price negotiation, 50% deposit, delivery date | amounts, promises, deadlines |
| 2 | Event planner + client for a wedding: several changes of mind | handling updates and contradictions |
| 3 | Supplier + shop: 3 orders, one unpaid invoice | "who owes me money" |
| 4 | Only voice notes, heavy Darija | transcription quality |
| 5 | Mostly small talk, almost no business content | the agent should extract **nothing**, not invent tasks |

For each test, write down the **expected items by hand**, then compare with what the agent extracts. Report a simple score in the submission, for example *"on 5 test chats, 41 of 46 expected items were extracted correctly, 0 invented items."* Real numbers from real tests impress judges.

---

## 6. Responsible AI and data (10 points, easy to collect)

- **Consent**: a chat export contains the *client's* messages too. For the demo, use only synthetic conversations or chats from people who agreed. In the product, show a notice asking the owner to inform clients.
- **Data minimization**: audio files are deleted after transcription; phone numbers are masked; data stays in a local database.
- **Human in control**: the agent never sends messages or makes calls; every draft is reviewed by the owner.
- **Honesty about limits**: Darija transcription is imperfect, especially with regional accents and noisy audio; low-confidence items are flagged.
- **Third-party APIs**: say clearly which providers receive the data (Groq, Google) and that production would need a data agreement or a local model.

---

## 7. Team roles (for a team of 4; merge roles if you are fewer)

| Person | Role | Owns |
|--------|------|------|
| **A** | AI pipeline | Parser, transcription, extraction, fallbacks, JSON validation |
| **B** | App and UI | Streamlit pages, database, deployment |
| **C** | Prompts and testing | Test conversations, voice notes, expected results, prompt tuning, scores |
| **D** | Product and pitch | User story, video script, recording, project sheet, AI tools declaration, submission forms |

With 2–3 people: A + B merge into one "builder," C + D into one "product and testing" person.

---

## 8. Sunday timeline (Tunis time = Moroccan time right now)

| Time | Official program | What our team does |
|------|------------------|--------------------|
| 08:30–09:00 | Check-in | Join official channels. Check internet (have a phone hotspot as backup). |
| 09:00–09:45 | Opening, hackathon story | **D** listens and notes rules and deliverables. **A, B** set up the repo, virtual environment, API keys, empty Streamlit app. |
| **09:45–10:00** | **Attendance check** | **Team leader confirms attendance before 10:00. Same team name and leader email as in the confirmation.** |
| 10:15–11:15 | NVIDIA talk | **D** watches (notes anything useful about NVIDIA Build). **A**: parser. **B**: DB and UI skeleton. **C**: finishes test chats and voice notes. |
| 11:15–11:30 | Sprint 1 | **A**: transcription working on 1 voice note end to end. |
| 11:30–11:45 | Mentor check | Pitch the idea in 30 seconds, ask: (1) is our "why not ChatGPT" convincing? (2) any rule concerns about pre-made test data? |
| 11:45–13:00 | Sprint 2 | **A**: extraction prompt + JSON validation. **B**: Import page + Client page showing items. **C**: runs tests, reports failures to A. **D**: drafts video script and project sheet. |
| 13:00–13:45 | Lunch | Eat. Quick team sync: what works, what's blocked. |
| 13:45–14:00 | Submission brief | **Everyone listens.** Note exact submission requirements. |
| 14:00–15:30 | Sprint 3 | **A**: brief + draft reply prompts, fallbacks. **B**: Dashboard, "who owes me money," source links. **C**: full test run, fills the score table. **D**: prepares the demo storyline. |
| **15:30** | **FEATURE FREEZE** | No new features after this. Only bug fixes. |
| 15:30–15:45 | Technical check | **B** deploys to Streamlit Cloud / HF Spaces. Test the public link on another device. |
| 15:45–16:30 | Final sprint | Fix bugs found in testing. **C** finalizes scores. **D** + one builder rehearse the demo. |
| **16:30–17:00** | | **Record the 90-second video** (see section 9). Finish project sheet and AI tools declaration. |
| **17:00–17:15** | | **SUBMIT.** Keep the confirmation. |
| 17:15–17:30 | Buffer | Only for emergencies. Never plan to submit at 17:29. |
| 17:30–19:15 | Judging | Prepare a 2–3 minute live demo in case we're in Morocco's top 3. |
| 19:15–19:45 | Live demos | Top 3 per country demo live. |

---

## 9. The 90-second video script

| Time | Content |
|------|---------|
| 0–15 s | **Problem.** "Youssef is a carpenter in Tangier. His whole business runs on WhatsApp: 60 voice notes a day in Darija. Last month he forgot a promised delivery and lost track of two unpaid deposits." |
| 15–25 s | **Why not ChatGPT.** One line: general assistants don't work on WhatsApp exports and Darija voice notes, don't remember his clients, and can invent details. |
| 25–65 s | **Live product.** Upload a chat export → voice notes transcribed → tasks, deadlines and payments appear with source links → open the "before calling Ahmed" brief → generate a follow-up message in Darija. |
| 65–80 s | **Proof.** "Tested on 5 real-style conversations: X/Y items correct, 0 invented. Low-confidence items are flagged. Nothing is ever sent without the owner's approval." |
| 80–90 s | **Next step.** WhatsApp Business API integration, pilot with 10 local businesses. Team name + project name. |

Tips: record the screen with real data, not slides. Speak slowly. Add subtitles (judges may watch without sound). Do one full dry run before recording.

---

## 10. Submission checklist

- [ ] Working prototype link (public, tested on another device and in a private browser window)
- [ ] 90-second video uploaded, link accessible without login
- [ ] Project sheet: name, one-sentence pitch, team members, tools, next step
- [ ] AI tools declaration: models used (Groq Whisper, Gemini, fallback), why we chose them, access constraints, what the AI actually does, fallback solution, NVIDIA Brev: **not used**
- [ ] Main prize selected in the dropdown
- [ ] Partner prize checkboxes, each with a short explanation of fit:
  - **Guepard** (AI-powered workflow/agent with a clear productivity gain): our strongest fit
  - **Yassir** (Morocco): everyday impact for local businesses
  - **Kredete** (financial inclusion): the "who owes me money" payment tracking, if the form allows it
  - **EY Studio+** (human-centered innovation): clear user and adoption path
  - **Thunders** (technical excellence): if our reliability and testing are strong
- [ ] Same team name and leader email as the confirmation form
- [ ] Screenshot of the submission confirmation

---

## 11. Likely jury questions (prepare answers)

1. **"Why not just use ChatGPT or WhatsApp's own AI?"** → Section 0 answer: Darija voice notes, per-client memory, structured actions, source-linked and verifiable.
2. **"How accurate is it on Darija?"** → Give the test numbers honestly, including failures, and show the low-confidence flag.
3. **"What about privacy? Clients didn't consent."** → Section 6: synthetic demo data, consent notice, audio deletion, human in control.
4. **"How would this reach real users?"** → Official WhatsApp Business API integration, freemium for small businesses, pilot with local artisans and suppliers.
5. **"What does it cost to run?"** → Rough estimate: one owner's daily messages cost a few cents of API usage; transcript caching keeps it low.

---

## 12. Tonight's prep checklist (Saturday, September 26)

Preparation only: **do not write the product code before Sunday**. The jury evaluates what is built during the hackathon.

- [ ] Confirm the team's final registration was submitted (due September 26)
- [ ] Create API keys: Google AI Studio (Gemini) and Groq; note the exact current model names
- [ ] **Test Darija transcription**: send 3–4 real Darija voice notes to Groq Whisper and Gemini in their web consoles. Compare quality. This decides the primary STT model.
- [ ] Export 2 test chats (Android + iPhone) to see the real file formats
- [ ] Install Python, Streamlit, ffmpeg on every laptop; create an empty GitHub repo
- [ ] Create Streamlit Community Cloud or Hugging Face accounts
- [ ] Write the 5 test scenarios and record the voice notes (test data, not product code; ask a mentor at 11:30 if unsure)
- [ ] Agree on roles and the team name; charge laptops; plan a backup internet connection
- [ ] Sleep. A rested team makes fewer bugs.
