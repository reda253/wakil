"""Test suite for D3 Data + Export Path.

Covers the two ways a chat gets into the database (exported .zip/.txt and the live
WhatsApp path) and the failures that produce a plausible-looking wrong answer rather
than a visible crash:

  * Android vs iPhone export layouts, 12h vs 24h clocks, French and English
  * re-importing the same chat must not duplicate messages or inflate money owed
  * every extracted item must resolve to a message that really exists
  * a malformed message must produce a warning, never vanish silently
  * phone numbers are masked on the way in and at rest

No test touches the real wakil.db: DB_PATH and UPLOAD_ROOT are redirected into a
temp directory in setUp, because core.db reads DB_PATH at call time inside connect().

Run with:  python -m pytest tests/test_d3_suite.py -v
"""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import ai, db, parser, pipeline, speech  # noqa: E402

# A 3 second clip would be a real ffmpeg call, and the audio bytes are irrelevant to
# anything asserted here, so transcription is faked.
FAKE_OPUS = b"not-really-opus"

# D1 is a real, live LLM.  These tests cover D3's plumbing - what gets stored, what
# gets de-duplicated, what a source id resolves to - so the model is faked at the
# boundary.  Without this the suite makes real API calls: it took 175 seconds, cost
# quota, and asserted whatever the model happened to return that day.
def fake_transcribe(audio_path):
    return {"text": f"transcribed: {os.path.basename(audio_path)}",
            "provider": "test"}


def fake_extract(client_name, messages, existing_items=None):
    """Cites the first message every time, so the id is stable across calls."""
    if not messages:
        return {"summary": f"{client_name}: nothing yet", "items": []}
    return {
        "summary": f"{client_name}: a deposit is expected.",
        "items": [{
            "type": "payment",
            "description": "50% deposit (7,500 MAD) to receive",
            "owner": "client",
            "amount_mad": 7500.0,
            "due_date": None,
            "source_message_id": messages[0]["id"],
            "confidence": "high",
            "status": "open",
        }],
    }

ANDROID_EN = (
    "Messages and calls are end-to-end encrypted. No one outside of this chat, "
    "not even WhatsApp, can read or listen to them.\n"
    "27/09/2026, 10:05 - Ahmed Benali: Salam, bghit cuisine kamla, ch7al taman?\n"
    "27/09/2026, 10:12 - Youssef: 15000 dh, khassni 50% avance w nsalik f 15 jours.\n"
    "27/09/2026, 10:14 - Ahmed Benali: Ok, ana ghadi nsiftlik l'avance ghedda.\n"
    "27/09/2026, 18:40 - Ahmed Benali: PTT-20260927-WA0001.opus (file attached)\n"
    "27/09/2026, 18:41 - Ahmed Benali: Wash katbghi 3 drawers w 2 placards?\n"
    "27/09/2026, 18:45 - Youssef deleted a message\n"
)

ANDROID_FR_12H = (
    "28/09/2026, 2:32 PM - Fatima: Bslama, bghit ncopi 3 tableaux pour 4500 dh, "
    "tele l'awdiyet rkhis?\n"
    "28/09/2026, 2:35 PM - Youssef: 4500 dh, 2000 f l'avance. Bezzaf safi 3 snin.\n"
    "28/09/2026, 2:36 PM - Fatima: PTT-20260928-WA0007.opus (fichier joint)\n"
)

# iOS: BOM, CRLF, U+200E before the attachment marker, seconds in the time.
IPHONE = (
    "\ufeff"
    "[27/09/2026, 10:05:22] Ahmed: Salam, bghit cuisine kamla, ch7al taman?\n"
    "[27/09/2026, 10:12:03] Youssef: 15000 dh, khassni 50% avance w nsalik f 15 jours.\n"
    "[27/09/2026, 18:40:11] Ahmed: \u200e<attached: "
    "00000042-AUDIO-2026-09-27-18-40-11.opus>\n"
    "[27/09/2026, 18:41:02] Ahmed: Ana m3ak,\nmerci bzaaf.\n"
).replace("\n", "\r\n")

IOS_AUDIO = "00000042-AUDIO-2026-09-27-18-40-11.opus"
ANDROID_AUDIO = "PTT-20260927-WA0001.opus"


class D3TestCase(unittest.TestCase):
    """Redirects the database and upload root into a temp dir for every test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wakil_d3_test_")
        self._real_db_path = db.DB_PATH
        self._real_upload_root = pipeline.UPLOAD_ROOT
        db.DB_PATH = os.path.join(self.tmp, "test.db")
        pipeline.UPLOAD_ROOT = os.path.join(self.tmp, "uploads")

        # D1 is a real LLM; fake it so this suite is fast, free and repeatable.
        for target, name, replacement in ((speech, "transcribe", fake_transcribe),
                                          (ai, "extract_items", fake_extract)):
            patcher = mock.patch.object(target, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.fixtures = os.path.join(self.tmp, "fixtures")
        os.makedirs(self.fixtures)
        self.android_txt = self._write("android_en.txt", ANDROID_EN)
        self.fr_txt = self._write("android_fr_12h.txt", ANDROID_FR_12H)
        self.iphone_txt = self._write("_chat.txt", IPHONE)

        self.android_zip = self._zip(
            "android_export.zip",
            {"WhatsApp Chat with Ahmed Benali/"
             "WhatsApp Chat with Ahmed Benali.txt": ANDROID_EN,
             ANDROID_AUDIO: FAKE_OPUS},
        )
        self.iphone_zip = self._zip(
            "iphone_export.zip", {"_chat.txt": IPHONE, IOS_AUDIO: FAKE_OPUS})

    def tearDown(self):
        db.DB_PATH = self._real_db_path
        pipeline.UPLOAD_ROOT = self._real_upload_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, text):
        path = os.path.join(self.fixtures, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _zip(self, name, files):
        path = os.path.join(self.fixtures, name)
        with zipfile.ZipFile(path, "w") as zf:
            for name_, body in files.items():
                zf.writestr(name_, body)
        return path


class TestParser(D3TestCase):
    """Reading the exported file."""

    def test_android_senders_and_timestamps(self):
        warnings = []
        client, messages = parser.parse_export(
            self.android_txt, "Youssef", warnings=warnings)
        self.assertEqual(client, "Ahmed Benali")
        # The encryption notice and the "deleted a message" system line are dropped.
        self.assertEqual(len(messages), 5)
        self.assertEqual([m["sender"] for m in messages],
                         ["client", "me", "client", "client", "client"])
        self.assertEqual([m["timestamp"] for m in messages],
                         ["2026-09-27T10:05", "2026-09-27T10:12", "2026-09-27T10:14",
                          "2026-09-27T18:40", "2026-09-27T18:41"])
        self.assertNotIn("deleted a message",
                         " ".join(m["content"] for m in messages))

    def test_android_voice_note_without_media_is_still_voice(self):
        _client, messages = parser.parse_export(self.android_txt, "Youssef")
        self.assertEqual(messages[3]["type"], "voice")
        self.assertIsNone(messages[3]["audio_path"])

    def test_android_missing_audio_is_warned_not_hidden(self):
        warnings = []
        parser.parse_export(self.android_txt, "Youssef", warnings=warnings)
        self.assertTrue(any("not in the archive" in w for w in warnings), warnings)

    def test_twelve_hour_clock_with_uppercase_pm(self):
        # A lowercase-only pattern made every real "2:32 PM" line invisible.
        _client, messages = parser.parse_export(self.fr_txt, "Youssef")
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["timestamp"], "2026-09-28T14:32")
        self.assertEqual(messages[2]["type"], "voice")
        self.assertIn("4500", messages[0]["content"])

    def test_iphone_layout_with_bom_crlf_and_lrm(self):
        warnings = []
        client, messages = parser.parse_export(
            self.iphone_txt, "Youssef", warnings=warnings)
        self.assertEqual(client, "Ahmed")
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[2]["type"], "voice")
        self.assertIn(IOS_AUDIO, messages[2]["content"])
        self.assertNotIn("\u200e", messages[2]["content"])
        # A wrapped message stays one message with its newline.
        self.assertIn("\n", messages[3]["content"])

    def test_unusual_date_and_time_separators(self):
        for body, expected in (
            ("27.09.2026, 10:05 - Ahmed: salam", "2026-09-27T10:05"),
            ("27-09-2026, 10:05 - Ahmed: salam", "2026-09-27T10:05"),
            ("27/09/26, 10:05 - Ahmed: salam", "2026-09-27T10:05"),
            ("[27/09/2026, 10:05] Ahmed: salam", "2026-09-27T10:05"),
        ):
            with self.subTest(body=body):
                path = self._write("odd.txt", body)
                _client, messages = parser.parse_export(path, "Youssef")
                self.assertEqual(messages[0]["timestamp"], expected)

    def test_garbage_and_empty_files_do_not_raise(self):
        for body in ("", "just some words", "27/09/2026, 10:05 - "):
            with self.subTest(body=body):
                path = self._write("junk.txt", body)
                client, messages = parser.parse_export(path, "Youssef")
                self.assertIsInstance(messages, list)
                self.assertIsInstance(client, str)


class TestOwnerResolution(D3TestCase):
    """Who is "me" decides who owes whom, so it is pinned down explicitly."""

    def _senders(self, owner):
        _client, messages = parser.parse_export(self.android_txt, owner)
        return "".join(m["sender"][0] for m in messages)

    def test_explicit_owner(self):
        self.assertEqual(self._senders("Youssef"), "cmccc")

    def test_owner_match_is_case_insensitive(self):
        self.assertEqual(self._senders("youssef"), "cmccc")

    def test_full_name_matches_a_chat_showing_only_a_first_name(self):
        self.assertEqual(self._senders("Youssef El Mansouri"), "cmccc")

    def test_naming_the_client_inverts_the_split(self):
        warnings = []
        _client, messages = parser.parse_export(
            self.android_txt, "Ahmed Benali", warnings=warnings)
        self.assertEqual("".join(m["sender"][0] for m in messages), "mcmmm")
        self.assertFalse([w for w in warnings if "does not appear" in w])

    def test_a_name_that_is_not_in_the_chat_warns(self):
        warnings = []
        parser.parse_export(self.android_txt, "Nobody Here", warnings=warnings)
        self.assertTrue(any("does not appear" in w for w in warnings), warnings)

    def test_missing_owner_name_says_the_split_is_a_guess(self):
        warnings = []
        parser.parse_export(self.android_txt, None, warnings=warnings)
        self.assertTrue(any("owner name given" in w for w in warnings), warnings)


class TestMasking(D3TestCase):
    """Masking must not eat the numbers that carry the meaning."""

    def test_phone_numbers_are_masked(self):
        self.assertEqual(parser.mask_phone("call +212 6 12 34 56 78 now"),
                         "call [PHONE] now")
        self.assertEqual(parser.mask_phone("0612345678"), "[PHONE]")
        self.assertEqual(parser.mask_phone("06 12 34 56 78"), "[PHONE]")
        self.assertEqual(parser.mask_phone("212612345678"), "[PHONE]")

    def test_amounts_dates_and_quantities_survive(self):
        for text in ("15000 dh", "1500000 dh", "3 drawers", "le 27/09/2026"):
            with self.subTest(text=text):
                self.assertEqual(parser.mask_phone(text), text)

    def test_amount_in_a_message_is_intact(self):
        _client, messages = parser.parse_export(self.android_txt, "Youssef")
        self.assertIn("15000", messages[1]["content"])


class TestExportPipeline(D3TestCase):
    """Unpack, transcribe, extract, store."""

    def setUp(self):
        super().setUp()
        self.stages = []
        self.client_id = pipeline.process_export(
            self.android_zip, "Youssef", client_phone="+212 6 12 34 56 78",
            progress_cb=lambda s, c=None, t=None: self.stages.append(s))

    def test_client_is_named_from_the_export(self):
        self.assertEqual(db.get_client(self.client_id)["name"], "Ahmed Benali")

    def test_all_messages_are_stored(self):
        self.assertEqual(len(db.get_messages(self.client_id)), 5)

    def test_voice_note_keeps_its_basename_and_gains_a_transcript(self):
        voice = [m for m in db.get_messages(self.client_id)
                 if m["type"] == "voice"][0]
        self.assertEqual(voice["content"], ANDROID_AUDIO)
        self.assertTrue(voice["transcript"])
        self.assertNotIn(self.tmp, voice["content"])

    def test_extracted_audio_is_deleted_after_transcription(self):
        # The responsible-AI claim: the owner's voice notes do not outlive the text.
        self.assertFalse(os.path.isdir(pipeline.UPLOAD_ROOT)
                         and os.listdir(pipeline.UPLOAD_ROOT))
        self.assertIn("Transcribing", self.stages)

    def test_every_source_is_an_export_message(self):
        self.assertEqual({m["source"] for m in db.get_messages(self.client_id)},
                         {"export"})

    def test_phone_is_masked_at_rest(self):
        self.assertEqual(db.get_client(self.client_id)["phone"], "[PHONE]")

    def test_every_item_resolves_to_a_real_source_message(self):
        for item in db.get_items(self.client_id):
            self.assertIsNotNone(
                db.get_source_message(item["source_message_id"], self.client_id))

    def test_items_carry_the_client_name(self):
        for item in db.get_items(self.client_id):
            self.assertEqual(item["client_name"], "Ahmed Benali")

    def test_money_owed_totals_the_extracted_items(self):
        self.assertEqual(db.get_money_owed()[0]["amount_mad"], 7500.0)

    def test_reimport_changes_nothing(self):
        # The original double-counting bug: new local ids meant UNIQUE never fired.
        before_items = len(db.get_items(self.client_id))
        before_owed = db.get_money_owed()[0]["amount_mad"]
        pipeline.process_export(self.android_zip, "Youssef")
        self.assertEqual(len(db.get_messages(self.client_id)), 5)
        self.assertEqual(len(db.get_items(self.client_id)), before_items)
        self.assertEqual(db.get_money_owed()[0]["amount_mad"], before_owed)

    def test_a_different_zip_is_a_separate_client(self):
        other = pipeline.process_export(self.iphone_zip, "Youssef")
        self.assertNotEqual(other, self.client_id)
        self.assertEqual(db.get_client(other)["name"], "Ahmed")
        self.assertEqual(len(db.get_messages(other)), 4)


class TestLivePipeline(D3TestCase):
    """Forwarded messages: stored, but only genuinely new items are returned."""

    def test_forwarded_messages_are_stored_as_the_client(self):
        pipeline.process_live_message("Karim Store", "text", "salam")
        client = db.get_clients()[0]
        messages = db.get_messages(client["id"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["source"], "whatsapp")
        self.assertEqual(messages[0]["sender"], "client")

    def test_local_ids_are_sequential_per_client(self):
        for text in ("salam", "3 drawers", "15000 dh"):
            pipeline.process_live_message("Karim Store", "text", text)
        client = db.get_clients()[0]
        self.assertEqual([m["local_id"] for m in db.get_messages(client["id"])],
                         [1, 2, 3])

    def test_a_new_item_is_returned_once_and_never_twice(self):
        # The fake extractor cites the first message, so the second call must dedupe.
        first = pipeline.process_live_message("Karim Store", "text", "salam")
        self.assertEqual(len(first), 1)
        self.assertEqual(
            pipeline.process_live_message("Karim Store", "text", "3 drawers"), [])
        client = db.get_clients()[0]
        self.assertEqual(len(db.get_items(client["id"])), 1)
        self.assertEqual(len(db.get_messages(client["id"])), 2)

    def test_an_item_pointing_at_a_missing_message_is_discarded_with_a_warning(self):
        with mock.patch.object(ai, "extract_items", side_effect=lambda name, msgs,
                               existing_items=None: {
            "summary": "s", "items": [{
                "type": "task", "description": "invented", "owner": "client",
                "amount_mad": None, "due_date": None, "source_message_id": 999,
                "confidence": "high", "status": "open"}]}):
            returned = pipeline.process_live_message("Karim Store", "text", "salam")
        self.assertEqual(returned, [])
        client = db.get_clients()[0]
        self.assertTrue(
            any("not in the chat" in w for w in pipeline.get_warnings(client["id"])),
            pipeline.get_warnings(client["id"]))

    def test_a_known_message_adds_nothing_and_changes_no_total(self):
        client_id = pipeline.process_export(self.android_zip, "Youssef")
        owed = db.get_money_owed()[0]["amount_mad"]
        self.assertEqual(
            pipeline.process_live_message(
                "Ahmed Benali", "text", "Wash katbghi 3 drawers w 2 placards?"), [])
        self.assertEqual(db.get_money_owed()[0]["amount_mad"], owed)
        self.assertEqual(len(db.get_items(client_id)), 1)


class TestStorageGuarantees(D3TestCase):
    """The schema and the shapes other devs' pages rely on."""

    def test_a_deleted_database_rebuilds_itself(self):
        db.get_clients()
        os.remove(db.DB_PATH)
        # Streamlit Community Cloud wipes the filesystem on redeploy.
        self.assertEqual(db.get_clients(), [])

    def test_an_older_database_is_rebuilt_rather_than_failing(self):
        db.get_clients()          # make sure the file exists
        os.remove(db.DB_PATH)
        legacy = sqlite3.connect(db.DB_PATH)
        legacy.executescript("""
            CREATE TABLE clients (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, phone TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL, local_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                sender TEXT NOT NULL CHECK (sender IN ('owner','client')),
                type TEXT NOT NULL, content TEXT, transcript TEXT,
                UNIQUE(client_id, local_id));
            INSERT INTO clients (name) VALUES ('Legacy Client');
            INSERT INTO messages (client_id, local_id, timestamp, sender, type, content)
                VALUES (1, 1, '2026-09-20T09:00', 'owner', 'text', 'salam');
        """)
        legacy.commit()
        legacy.close()
        # The old CHECK would reject every insert of 'me'.
        client_id = pipeline.process_export(self.android_zip, "Youssef")
        self.assertEqual(len(db.get_messages(client_id)), 5)
        self.assertLessEqual({m["sender"] for m in db.get_messages(client_id)},
                             {"me", "client"})

    def test_a_fresh_database_does_not_claim_to_have_been_rebuilt(self):
        db.get_clients()          # make sure the file exists
        os.remove(db.DB_PATH)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            db.get_clients()
        self.assertEqual(buffer.getvalue(), "")

    def test_a_malformed_message_is_warned_about_not_dropped_silently(self):
        # This is the fix: any IntegrityError used to be counted as a duplicate, so
        # a bad message vanished and the dashboard showed an incomplete chat.
        client_id = db.get_or_create_client("Test")
        problems = []
        inserted, skipped = db.save_messages(client_id, [
            {"local_id": 1, "timestamp": "2026-09-27T10:00", "sender": "client",
             "type": "video", "content": "a clip"},
            {"local_id": 2, "timestamp": "2026-09-27T10:01", "sender": "client",
             "type": None, "content": "salam"},
        ], problems=problems)
        self.assertEqual(inserted, 2)
        self.assertEqual(skipped, 0)
        self.assertTrue(any("stored as text" in p for p in problems), problems)
        stored = db.get_messages(client_id)
        self.assertEqual([m["type"] for m in stored], ["text", "text"])

    def test_a_duplicate_is_skipped_without_a_warning(self):
        client_id = db.get_or_create_client("Test")
        row = {"local_id": 1, "timestamp": "2026-09-27T10:00", "sender": "client",
               "type": "text", "content": "salam"}
        db.save_messages(client_id, [row])
        problems = []
        inserted, skipped = db.save_messages(client_id, [row], problems=problems)
        self.assertEqual((inserted, skipped), (0, 1))
        self.assertEqual(problems, [])

    def test_a_message_with_no_id_is_reported(self):
        client_id = db.get_or_create_client("Test")
        problems = []
        db.save_messages(client_id, [
            {"local_id": None, "timestamp": "2026-09-27T10:00", "sender": "me",
             "content": "orphan"}], problems=problems)
        self.assertTrue(any("no id" in p for p in problems), problems)

    def test_saving_without_a_problems_list_fails_loudly(self):
        client_id = db.get_or_create_client("Test")
        with self.assertRaises(ValueError):
            db.save_messages(client_id, [
                {"local_id": None, "timestamp": "2026-09-27T10:00",
                 "sender": "me", "content": "orphan"}])

    def test_sender_vocabulary_from_contracts_is_accepted(self):
        client_id = db.get_or_create_client("Test")
        db.save_messages(client_id, [
            {"local_id": 1, "timestamp": "2026-09-27T10:00", "sender": "owner",
             "type": "text", "content": "salam"}])
        self.assertEqual(db.get_messages(client_id)[0]["sender"], "me")

    def test_source_lookup_accepts_either_id_space(self):
        client_id = db.get_or_create_client("Test")
        db.save_messages(client_id, [
            {"local_id": 7, "timestamp": "2026-09-27T10:00", "sender": "client",
             "type": "text", "content": "salam"}])
        by_local = db.get_message(7, client_id)
        by_row = db.get_message(by_local["id"], client_id)
        self.assertEqual(by_local["content"], by_row["content"])

    def test_read_shapes_the_ui_depends_on(self):
        client_id = db.get_or_create_client("Ahmed", phone="0612345678")
        db.save_messages(client_id, [
            {"local_id": 1, "timestamp": "2026-09-27T10:00", "sender": "client",
             "type": "text", "content": "salam"}])
        db.save_items(client_id, [{
            "type": "payment", "description": "deposit", "owner": "client",
            "amount_mad": 7500.0, "due_date": None, "source_message_id": 1,
            "confidence": "high"}])
        self.assertEqual(db.get_client(client_id)["phone"], "[PHONE]")
        self.assertEqual(len(db.get_items(client_id, "open")), 1)
        self.assertEqual(len(db.get_items(client_id, status=None)), 1)
        item = db.get_items(client_id)[0]
        for key in ("id", "type", "description", "owner", "amount_mad", "due_date",
                    "status", "source_message_id", "confidence", "client_name"):
            self.assertIn(key, item)
        self.assertEqual(len(db.get_messages(client_id, limit=1)), 1)
        self.assertEqual(db.get_money_owed()[0],
                         {"client": "Ahmed", "amount_mad": 7500.0})
        self.assertIsNone(db.set_item_status(item["id"], "done"))
        self.assertEqual(len(db.get_items(client_id, "open")), 0)
        self.assertEqual(db.get_money_owed(), [])


if __name__ == "__main__":
    unittest.main()
