"""Score the pipeline against hand-written expected items.  Owner: P4.

Layout:
  tests/data/<scenario>/chat.txt (or .zip)
  tests/data/<scenario>/expected.json   -> {"items": [Item, ...]}

Prints per chat: correct, missed, INVENTED, seconds. Run: python -m tests.evaluate
"""
import json
import time
from pathlib import Path

import ai
import parser as wa_parser

DATA = Path(__file__).parent / "data"


def match(expected, got):
    """Loose match: same type, owner, amount and due date. Tune as needed."""
    return (expected["type"] == got["type"] and expected["owner"] == got["owner"]
            and expected.get("amount_mad") == got.get("amount_mad")
            and expected.get("due_date") == got.get("due_date"))


def run():
    total_expected = total_correct = total_invented = 0
    for scenario in sorted(p for p in DATA.iterdir() if p.is_dir()):
        chat = next(scenario.glob("chat.*"), None)
        exp_file = scenario / "expected.json"
        if not chat or not exp_file.exists():
            continue
        expected = json.loads(exp_file.read_text(encoding="utf-8"))["items"]
        start = time.time()
        client_name, messages = wa_parser.parse_export(str(chat))
        got = ai.extract_items(client_name, messages)["items"]
        secs = time.time() - start

        remaining = list(got)
        correct = 0
        for e in expected:
            hit = next((g for g in remaining if match(e, g)), None)
            if hit:
                correct += 1
                remaining.remove(hit)
        invented = len(remaining)
        total_expected += len(expected)
        total_correct += correct
        total_invented += invented
        print(f"{scenario.name:30} correct {correct}/{len(expected)}  missed {len(expected) - correct}"
              f"  invented {invented}  {secs:.1f}s")
    print(f"\nTOTAL: {total_correct}/{total_expected} correct, {total_invented} invented")


if __name__ == "__main__":
    run()
