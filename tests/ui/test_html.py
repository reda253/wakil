import re
import tomllib
from datetime import date
from pathlib import Path

from tests.ui.conftest import CLIENTS, MESSAGES, OWED, open_items
from ui import html as h
from ui import theme
from ui import viewmodel as vm

T = date(2026, 9, 27)
ROOT = Path(__file__).resolve().parents[2]
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


def test_esc():
    assert h.esc('<a href="x">&') == "&lt;a href=&quot;x&quot;&gt;&amp;"
    assert h.esc(None) == "" and h.esc(12) == "12"


def test_badge_default_neutral_and_escaped():
    assert h.badge("<i>x</i>", "accent") == '<span class="w-badge w-accent">&lt;i&gt;x&lt;/i&gt;</span>'
    assert 'w-neutral' in h.badge("x")


def test_item_html_escapes_description():
    item = dict(open_items()[0], description="<script>alert(1)</script>")
    out = h.item_html(item, "Ahmed", T)
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_item_html_states():
    low = h.item_html(open_items()[1], "Ahmed", T, source="whatsapp")
    assert "w-low" in low and "Needs check" in low and "w-warn" in low
    assert "via WhatsApp" in low and "Due today" in low
    high = h.item_html(open_items()[0], None, T)
    assert "Needs check" not in high and "7,500 MAD" in high
    assert "2 days late" in high and "w-danger" in high


def test_item_html_urgency_badge():
    urgent = h.item_html(open_items()[4], "Sara", T, urgency="urgent")
    assert ">Urgent<" in urgent and "w-danger" in urgent
    normal = h.item_html(open_items()[2], "Sara", T, urgency="normal")
    assert ">Normal<" in normal and "w-danger" not in normal


def test_owed_row_html_neutral_avatar():
    row = vm.owed_rows(OWED, open_items(), CLIENTS, T)[0]
    out = h.owed_row_html(row)
    assert "w-overdue" in out and "Ahmed Benali" in out and "7,500 MAD" in out
    assert '<span class="w-avatar">AB</span>' in out


def test_metric_html():
    out = h.metric_html("payments", "Owed to you", "7,500", "MAD")
    assert '<span class="w-ico" aria-hidden="true">payments</span>' in out
    assert "7,500" in out and "MAD" in out and "Owed to you" in out
    assert "w-unit" not in h.metric_html("inventory_2", "Open orders", 4)


def test_kv_html_escapes():
    out = h.kv_html([("<b>Sara</b>", "1 & 2")])
    assert "&lt;b&gt;Sara&lt;/b&gt;" in out and "1 &amp; 2" in out


def test_brief_html():
    out = h.brief_html([("Status", "a <b>"), ("", "free line")])
    assert out.count("<li>") == 2 and ">1<" in out and ">2<" in out
    assert "<b>Status:</b>" in out and "a &lt;b&gt;" in out


def test_message_html_escapes_body():
    out = h.message_html(MESSAGES[0])
    assert "&lt;b&gt;now&lt;/b&gt;" in out and "w-theirs" in out


def test_message_html_voice_and_owner():
    voice = h.message_html(MESSAGES[1])
    assert "Voice note" in voice and "via WhatsApp" in voice and "deposit Friday" in voice
    assert "not transcribed yet" in h.message_html(dict(MESSAGES[1], transcript=None))
    assert "w-mine" in h.message_html(MESSAGES[2])
    # core/db.py stores the owner as "me" and exposes the per-chat local_id
    stored = h.message_html(dict(MESSAGES[2], sender="me", id=987, local_id=3))
    assert "w-mine" in stored and "#3 " in stored and "987" not in stored


def test_client_header_html():
    out = h.client_header_html(CLIENTS[0], 3, 7500.0)
    assert "Ahmed Benali" in out and "3 open items" in out and "7,500 MAD" in out
    assert "Nothing owed" in h.client_header_html(CLIENTS[1], 0, 0)


def test_theme_is_restrained():
    css = theme.css()
    assert css.startswith("<style>") and css.endswith("</style>")
    assert "--w-accent:#CCF062" in css and "--w-canvas:#FDFBF7" in css
    assert theme.TONES == ("neutral", "accent", "danger", "warn")
    for tone in theme.TONES:
        assert f".w-{tone}{{" in css
    for banned in ("lilac", "peach", "sky", "mint"):
        assert banned not in css


def test_streamlit_config_matches_design():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    t = cfg["theme"]
    assert t["primaryColor"] == "#CCF062" and t["backgroundColor"] == "#FDFBF7"
    assert t["textColor"] == "#0F172A" and "Plus Jakarta Sans" in t["font"]
    assert cfg["server"]["maxUploadSize"] == 200


def test_no_emoji_in_ui_sources():
    files = [ROOT / "app.py", *sorted((ROOT / "ui").glob("*.py")),
             *[ROOT / "pages" / n for n in ("2_Dashboard.py", "3_Client.py", "4_Brief_Reply.py", "5_Orders.py")]]
    for f in files:
        if f.exists():
            assert not EMOJI.search(f.read_text(encoding="utf-8")), f"emoji found in {f.name}"


def test_visual_round_fixes():
    css = theme.css()
    # selected segmented pill must use dark text (lime-on-lime was unreadable)
    assert 'button[data-variant="segmented_control"][aria-checked="true"]' in css
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["client"]["toolbarMode"] == "minimal"  # hides Streamlit's Deploy menu
    src = (ROOT / "ui" / "components.py").read_text(encoding="utf-8")
    assert 'st.popover("Details")' in src  # no second chevron icon
