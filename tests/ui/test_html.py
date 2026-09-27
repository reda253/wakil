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
    assert "--w-accent:#CCF062" in css and "--w-canvas:light-dark(#FDFBF7," in css
    assert theme.TONES == ("neutral", "accent", "danger", "warn")
    for tone in theme.TONES:
        assert f".w-{tone}{{" in css
    for banned in ("lilac", "peach", "sky", "mint"):
        assert banned not in css


def test_streamlit_config_matches_design():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    t, light = cfg["theme"], cfg["theme"]["light"]
    assert light["primaryColor"] == "#CCF062" and light["backgroundColor"] == "#FDFBF7"
    assert light["textColor"] == "#0F172A" and "Plus Jakarta Sans" in t["font"]
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
    assert cfg["client"]["toolbarMode"] == "viewer"  # hides Deploy, keeps the theme switch
    src = (ROOT / "ui" / "components.py").read_text(encoding="utf-8")
    assert 'st.popover("Details")' in src  # no second chevron icon


def test_client_header_hides_masked_phone():
    assert "[PHONE]" not in h.client_header_html(dict(CLIENTS[0], phone="[PHONE]"), 1, 0)
    assert "+212600000001" in h.client_header_html(CLIENTS[0], 1, 0)


def test_hero_html_escapes():
    out = h.hero_html("Sunday 27 September", "<b>2</b> items late.")
    assert "w-hero-title" in out and "&lt;b&gt;2&lt;/b&gt;" in out and "Sunday 27 September" in out


def test_order_row_html():
    row = vm.orders(open_items(), CLIENTS, T)[0]
    out = h.order_row_html(row)
    assert ">Urgent<" in out and "w-danger" in out
    assert "Cut fabric for curtains" in out and "Sara · 1 day late" in out


def test_order_row_html_escapes():
    row = dict(vm.orders(open_items(), CLIENTS, T)[1], client="<i>X</i>")
    row["item"] = dict(row["item"], description="<script>x</script>")
    out = h.order_row_html(row)
    assert "<script>" not in out and "&lt;i&gt;X&lt;/i&gt;" in out and ">High<" in out and "w-danger" not in out


def test_theme_has_one_brand_color_for_the_hero():
    css = theme.css()
    assert "--w-brand:#173B35" in css and ".st-key-hero{" in css
    assert "prefers-reduced-motion:no-preference" in css
    motion = css.split("@media (prefers-reduced-motion:no-preference){", 1)[1]
    assert css.count("scale(.97)") == motion.count("scale(.97)") > 0  # all press motion is motion-safe
    assert ".stMainBlockContainer{padding-top:6rem" in css  # clears the taller fixed header (76px) + 20px


def test_hero_tiles_stay_two_per_row_on_phones():
    css = theme.css()
    phone = css.split("@media (max-width:640px){", 1)[1]
    assert '.st-key-hero [data-testid="stHorizontalBlock"]{flex-wrap:wrap' in phone
    assert '.st-key-hero [data-testid="stColumn"]{' in phone


def test_bigger_logo_and_top_tabs():
    css = theme.css()
    assert '[data-testid="stHeader"]{height:76px' in css
    assert '[data-testid="stHeaderLogo"]{height:60px' in css
    assert '[data-testid="stTopNavLink"]{height:38px' in css and "font-size:16px" in css


def test_logo_asset_is_cropped_to_the_mark():
    from PIL import Image
    im = Image.open(Path(__file__).resolve().parents[2] / "ui" / "assets" / "logo.png")
    from PIL import ImageChops
    rgb = im.convert("RGB")
    w, h = rgb.size
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    left, top, right, bottom = ImageChops.difference(rgb, bg).convert("L").point(
        lambda v: 255 if v > 24 else 0).getbbox()
    # the mark fills the tile instead of floating in a wide margin (it was ~45% before)
    assert w == h and max(right - left, bottom - top) >= 0.75 * w


def test_custom_colors_follow_the_streamlit_theme():
    css = theme.css()
    # every themed token resolves against the color-scheme Streamlit sets on the app
    assert "--w-text:light-dark(#0F172A,#E7ECE9)" in css
    assert "--w-canvas:light-dark(#FDFBF7,#111514)" in css
    assert "--w-brand:#173B35" in css  # the one brand color is the same in both themes
    # text on the lime primary button stays dark in dark mode
    assert '[data-testid="stBaseButton-primary"]{color:var(--w-on-accent)' in css
    assert "--w-on-accent:#0F172A" in css


def test_config_offers_light_and_dark_themes():
    import tomllib
    cfg = tomllib.loads((Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml").read_text("utf-8"))
    assert cfg["client"]["toolbarMode"] == "viewer"  # keeps the viewer theme switch, hides Deploy
    light, dark = cfg["theme"]["light"], cfg["theme"]["dark"]
    assert light["backgroundColor"] == theme.TOKENS["canvas"][0]
    assert dark["backgroundColor"] == theme.TOKENS["canvas"][1]
    assert dark["textColor"] == theme.TOKENS["text"][1]
    assert "base" not in cfg["theme"]  # a fixed base would pin one theme
