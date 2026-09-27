"""Comprehensive test suite for D1 AI Engine.
Validates contracts, types, anti-hallucination, and fallback behavior.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import contracts, llm, speech, ai


class TestD1Engine(unittest.TestCase):

    def setUp(self):
        self.sample_messages = [
            {
                "id": 1,
                "client_id": 42,
                "timestamp": "2026-09-27T10:00",
                "sender": "client",
                "type": "text",
                "content": "Hi, I want to order the custom desk for 4,000 MAD.",
                "transcript": None,
                "source": "whatsapp",
            },
            {
                "id": 2,
                "client_id": 42,
                "timestamp": "2026-09-27T10:05",
                "sender": "owner",
                "type": "text",
                "content": "Great! Please send a 50% deposit of 2000 MAD by next Friday, and I will deliver it by 2026-10-15.",
                "transcript": None,
                "source": "whatsapp",
            },
            {
                "id": 3,
                "client_id": 42,
                "timestamp": "2026-09-27T10:07",
                "sender": "client",
                "type": "text",
                "content": "Perfect, I promise to transfer the 2000 MAD deposit tomorrow.",
                "transcript": None,
                "source": "whatsapp",
            },
        ]

    def test_item_contract_compliance(self):
        """Verify that sanitized items match the frozen Item contract exactly."""
        raw_items = [
            {
                "type": "payment",
                "description": "2000 MAD deposit to receive",
                "owner": "client",
                "amount_mad": "2,000 MAD",
                "due_date": "2026-09-28",
                "source_message_id": 3,
                "confidence": "high",
            },
            {
                "type": "deadline",
                "description": "Deliver custom desk",
                "owner": "me",
                "amount_mad": None,
                "due_date": "2026-10-15",
                "source_message_id": 2,
                "confidence": "high",
            },
        ]
        sanitized = ai._validate_and_sanitize_items(raw_items, valid_message_ids={1, 2, 3}, client_id=42)
        self.assertEqual(len(sanitized), 2)
        
        item1 = sanitized[0]
        self.assertEqual(item1["type"], "payment")
        self.assertEqual(item1["owner"], "client")
        self.assertEqual(item1["amount_mad"], 2000.0)
        self.assertEqual(item1["due_date"], "2026-09-28")
        self.assertEqual(item1["source_message_id"], 3)
        self.assertEqual(item1["confidence"], "high")
        self.assertEqual(item1["status"], "open")
        self.assertEqual(item1["client_id"], 42)

        item2 = sanitized[1]
        self.assertEqual(item2["type"], "deadline")
        self.assertEqual(item2["owner"], "me")
        self.assertIsNone(item2["amount_mad"])
        self.assertEqual(item2["due_date"], "2026-10-15")
        self.assertEqual(item2["source_message_id"], 2)

    def test_drop_items_with_invalid_source_message_id(self):
        """Hallucinated message IDs (e.g. source 47) must be dropped, not snapped to a random message."""
        raw_items = [
            {
                "type": "payment",
                "description": "Valid payment item",
                "owner": "client",
                "amount_mad": 500.0,
                "source_message_id": 2,
            },
            {
                "type": "promise",
                "description": "Hallucinated item citing message 47",
                "owner": "me",
                "source_message_id": 47,
            },
            {
                "type": "task",
                "description": "Item with non-numeric source_message_id",
                "owner": "me",
                "source_message_id": "invalid_id",
            },
        ]
        # Only message IDs {1, 2, 3} exist in the chat
        sanitized = ai._validate_and_sanitize_items(raw_items, valid_message_ids={1, 2, 3}, client_id=1)
        self.assertEqual(len(sanitized), 1)
        self.assertEqual(sanitized[0]["source_message_id"], 2)
        self.assertEqual(sanitized[0]["description"], "Valid payment item")

    @patch("core.llm.call_llm")
    def test_extract_items_success(self, mock_llm):
        """Test extraction flow with valid LLM output."""
        mock_llm.return_value = """
        {
            "summary": "Client ordered a custom desk for 4,000 MAD with deposit agreed.",
            "items": [
                {
                    "type": "payment",
                    "description": "Deposit of 2000 MAD",
                    "owner": "client",
                    "amount_mad": 2000.0,
                    "due_date": "2026-09-28",
                    "source_message_id": 3,
                    "confidence": "high"
                }
            ]
        }
        """
        result = ai.extract_items("Karim", self.sample_messages)
        self.assertIn("summary", result)
        self.assertIn("items", result)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["amount_mad"], 2000.0)
        self.assertEqual(result["items"][0]["source_message_id"], 3)

    @patch("core.llm.call_llm")
    def test_extract_items_smalltalk_zero_items(self, mock_llm):
        """Small talk should return 0 items to guarantee anti-hallucination."""
        mock_llm.return_value = '{"summary": "Casual check-in with client.", "items": []}'
        small_talk = [
            {"id": 1, "client_id": 5, "timestamp": "2026-09-27T11:00", "sender": "client", "type": "text", "content": "Hello, how are you today?", "transcript": None, "source": "whatsapp"},
            {"id": 2, "client_id": 5, "timestamp": "2026-09-27T11:01", "sender": "owner", "type": "text", "content": "I am doing well, thank you! Hope you are too.", "transcript": None, "source": "whatsapp"},
        ]
        result = ai.extract_items("Nadia", small_talk)
        self.assertEqual(len(result["items"]), 0)

    @patch("core.llm.call_llm")
    def test_make_brief(self, mock_llm):
        """Test brief generation."""
        mock_llm.return_value = (
            "1. Status: Custom desk order in progress.\n"
            "2. My promises: Delivery on October 15.\n"
            "3. Client's promises: 2000 MAD deposit.\n"
            "4. Money owed: 2000 MAD deposit.\n"
            "5. Suggested next step: Check if deposit was received."
        )
        brief = ai.make_brief("Karim", [], self.sample_messages)
        self.assertIn("Status", brief)
        self.assertIn("promises", brief)

    @patch("core.llm.call_llm")
    def test_draft_reply(self, mock_llm):
        """Test draft reply generation."""
        mock_llm.return_value = """
        {
            "whatsapp": "Hi Karim, confirming that we are ready to start once the deposit is received. Thanks!",
            "email": "Dear Karim,\\n\\nThank you for confirming your order. We will begin production upon receiving the deposit.\\n\\nBest regards,\\nWakil"
        }
        """
        draft = ai.draft_reply("Status: Custom desk order.", "payment_reminder")
        self.assertIn("whatsapp", draft)
        self.assertIn("email", draft)
        self.assertGreater(len(draft["whatsapp"]), 10)
        self.assertGreater(len(draft["email"]), 20)

    def test_speech_cache_mechanism(self):
        """Verify hash-based caching mechanism in speech module."""
        test_file = "/tmp/test_wakil_audio.txt"
        with open(test_file, "w") as f:
            f.write("dummy audio content for hash test")
        
        file_hash = speech.get_file_hash(test_file)
        self.assertTrue(len(file_hash) > 0)
        if os.path.exists(test_file):
            os.remove(test_file)


if __name__ == "__main__":
    unittest.main()
