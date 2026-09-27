"""Calm design tokens derived from the Stitch system, restrained to one accent.  Owner: D4."""
import streamlit as st

TOKENS = {
    "canvas": "#FDFBF7", "card": "#FFFFFF", "subtle": "#F7F5F0",
    "border": "#EBE8E1", "border_strong": "#CBD5E1",
    "text": "#0F172A", "muted": "#64748B",
    "brand": "#173B35",
    "accent": "#CCF062", "accent_deep": "#A3D422", "accent_soft": "#F2FBD2",
    "danger": "#BA1A1A", "danger_soft": "#FFDAD6",
    "warn": "#9A3412", "warn_soft": "#FFF3E6",
}
TONES = ("neutral", "accent", "danger", "warn")

_ICON_FONT = ("@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:"
              "opsz,wght,FILL,GRAD@20..48,400,0,0&display=block');")

_CSS = (
    # badges: exactly four tones
    ".w-badge{display:inline-flex;align-items:center;padding:2px 10px;border-radius:9999px;font-size:11px;"
    "line-height:16px;font-weight:600;letter-spacing:.02em;white-space:nowrap}"
    ".w-neutral{background:var(--w-subtle);color:var(--w-muted)}"
    ".w-accent{background:var(--w-accent-soft);color:var(--w-text)}"
    ".w-danger{background:var(--w-danger-soft);color:var(--w-danger)}"
    ".w-warn{background:var(--w-warn-soft);color:var(--w-warn)}"
    # metric cards: one monochrome icon tile, one number, one label
    ".w-metric{display:flex;flex-direction:column;gap:2px}"
    ".w-ico{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;"
    "letter-spacing:normal;text-transform:none;white-space:nowrap;direction:ltr;font-feature-settings:'liga';"
    "width:36px;height:36px;border-radius:10px;background:var(--w-subtle);color:var(--w-text);"
    "display:inline-flex;align-items:center;justify-content:center;margin-bottom:10px}"
    ".w-metric-value{font-size:32px;line-height:40px;font-weight:700;letter-spacing:-.02em;color:var(--w-text);"
    "font-variant-numeric:tabular-nums}"
    ".w-unit{font-size:15px;font-weight:600;color:var(--w-muted)}"
    ".w-caption{font-size:13px;line-height:18px;color:var(--w-muted)}"
    ".w-muted{font-size:12px;font-weight:600;color:var(--w-muted)}"
    ".w-kv-list{display:flex;flex-direction:column;gap:6px;margin-top:6px}"
    ".w-kv{display:flex;justify-content:space-between;gap:12px;font-size:13px;color:var(--w-muted)}"
    ".w-kv b{color:var(--w-text);font-weight:600;text-align:right}"
    # rows and avatars: every person gets the same neutral circle
    ".w-row{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}"
    ".w-row-left{display:flex;align-items:center;gap:12px}"
    ".w-row-title{font-size:14px;font-weight:700;color:var(--w-text);display:flex;gap:8px;align-items:center;flex-wrap:wrap}"
    ".w-row-right{text-align:right}"
    ".w-amount{font-size:18px;font-weight:700;color:var(--w-text);font-variant-numeric:tabular-nums}"
    ".w-overdue .w-amount{color:var(--w-danger)}"
    ".w-avatar{width:40px;height:40px;border-radius:9999px;display:inline-flex;align-items:center;justify-content:center;"
    "font-weight:700;font-size:13px;color:var(--w-text);background:var(--w-subtle);border:1px solid var(--w-border);flex-shrink:0}"
    ".w-avatar-lg{width:52px;height:52px;font-size:16px}"
    # items
    ".w-chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px}"
    ".w-item-desc{font-size:14px;line-height:22px;font-weight:600;color:var(--w-text)}"
    ".w-item.w-low{border-left:3px solid var(--w-warn);padding-left:10px}"
    ".w-item.w-done .w-item-desc{text-decoration:line-through;color:var(--w-muted)}"
    # brief, notices, empty states
    ".w-brief{background:var(--w-subtle);border-radius:16px;padding:16px}"
    ".w-eyebrow{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--w-muted);margin-bottom:8px}"
    ".w-brief ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}"
    ".w-brief li{display:flex;gap:10px;font-size:13px;line-height:20px;color:var(--w-text)}"
    ".w-num{width:20px;height:20px;border-radius:9999px;display:inline-flex;align-items:center;justify-content:center;"
    "font-size:11px;font-weight:700;flex-shrink:0;background:var(--w-card);border:1px solid var(--w-border)}"
    ".w-notice{background:var(--w-subtle);border-radius:12px;padding:12px;font-size:13px;color:var(--w-muted)}"
    ".w-notice b{color:var(--w-text)}"
    ".w-empty{border:1px dashed var(--w-border-strong);border-radius:16px;padding:24px;text-align:center;"
    "color:var(--w-muted);font-size:14px}"
    # chat history
    ".w-msg{max-width:80%;margin:8px 0;padding:10px 14px;border-radius:16px;border:1px solid var(--w-border);background:var(--w-card)}"
    ".w-msg.w-mine{margin-left:auto;background:var(--w-subtle)}"
    ".w-msg-meta{font-size:11px;color:var(--w-muted);display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:4px}"
    ".w-msg-body,.w-quote{font-size:14px;line-height:22px;color:var(--w-text);white-space:pre-wrap}"
    ".w-client-head{display:flex;align-items:center;gap:14px;flex-wrap:wrap}"
    ".w-client-name{font-size:24px;line-height:32px;font-weight:700;color:var(--w-text)}"
    # Streamlit overrides: dark text on the lime primary button
    '[data-testid="stBaseButton-primary"]{color:var(--w-text)!important;font-weight:700!important}'
    '[data-testid="stBaseButton-primary"]:hover{background:var(--w-accent-deep)!important;border-color:var(--w-accent-deep)!important}'
    # selected filter pill: Streamlit paints its text lime on a lime tint, unreadable
    'button[data-variant="segmented_control"][aria-checked="true"]{color:var(--w-text)!important;'
    "background:var(--w-accent-soft)!important;border-color:var(--w-accent-deep)!important;font-weight:600}"
    # density: less dead space above and between blocks
    ".stMainBlockContainer{padding-top:5rem!important;padding-bottom:3rem!important;max-width:1320px!important}"
    ".stApp h1{font-size:30px!important;line-height:38px!important;letter-spacing:-.02em!important;padding:0 0 .25rem!important}"
    ".stApp h3{font-size:18px!important;line-height:26px!important;padding:0 0 .25rem!important}"
    # top bar: bigger logo (fits the 60px header) and bigger nav tabs
    '[data-testid="stHeaderLogo"]{height:48px!important;max-height:48px!important;width:auto!important}'
    '[data-testid="stTopNavLink"]{height:38px!important;padding:0 14px!important;gap:8px}'
    '[data-testid="stTopNavLink"] p,[data-testid="stTopNavLink"] span{font-size:16px!important;line-height:20px!important;font-weight:600}'
    '[data-testid="stTopNavLink"] [data-testid="stIconMaterial"]{font-size:20px!important}'
    # the one brand color: the dashboard 'Today' hero band
    ".st-key-hero{background:var(--w-brand);border-radius:20px;padding:20px 22px 22px}"
    ".w-hero-eyebrow{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--w-accent)}"
    ".w-hero-title{font-size:26px;line-height:34px;font-weight:700;letter-spacing:-.02em;color:#FFFFFF;margin-top:4px}"
    '.st-key-hero [class*="st-key-metric_"]{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);'
    "border-radius:14px;padding:14px 16px}"
    ".st-key-hero .w-metric-value{color:#FFFFFF}"
    ".st-key-hero .w-caption,.st-key-hero .w-unit{color:rgba(255,255,255,.68)}"
    ".st-key-hero .w-ico{background:rgba(204,240,98,.16);color:var(--w-accent)}"
    '.st-key-hero [data-testid="stPopoverButton"]{background:transparent!important;color:rgba(255,255,255,.88)!important;'
    "border-color:rgba(255,255,255,.22)!important}"
    # phones: keep the hero tiles 2 per row instead of 4 full-width stacked cards
    "@media (max-width:640px){"
    '.st-key-hero [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.6rem!important}'
    '.st-key-hero [data-testid="stColumn"]{flex:1 1 calc(50% - .3rem)!important;min-width:calc(50% - .3rem)!important;width:auto!important}'
    '.st-key-hero [class*="st-key-metric_"]{padding:12px}'
    ".st-key-hero .w-ico{width:30px;height:30px;font-size:18px;margin-bottom:6px}"
    ".st-key-hero .w-metric-value{font-size:24px;line-height:30px}"
    ".w-hero-title{font-size:22px;line-height:28px}"
    "}"
    # 'Next to deliver' list
    ".w-order{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--w-border)}"
    ".w-order:first-child{border-top:0;padding-top:0}"
    ".w-order .w-badge{margin-top:2px;min-width:60px;justify-content:center}"
    ".w-order-desc{font-size:14px;line-height:20px;font-weight:600;color:var(--w-text)}"
    # press feedback (emil-design-eng): transform only, fast strong ease-out, motion-safe
    "@media (prefers-reduced-motion:no-preference){"
    '[data-testid="stButton"] button,[data-testid="stPopoverButton"],[data-testid="stLinkButton"] a,'
    'button[data-variant="segmented_control"]{transition:transform 160ms cubic-bezier(.23,1,.32,1),'
    "background-color 150ms ease,border-color 150ms ease}"
    '[data-testid="stButton"] button:active,[data-testid="stPopoverButton"]:active,[data-testid="stLinkButton"] a:active,'
    'button[data-variant="segmented_control"]:active{transform:scale(.97)}'
    "}"
)


def css():
    root = ";".join(f"--w-{k.replace('_', '-')}:{v}" for k, v in TOKENS.items())
    return f"<style>{_ICON_FONT}:root{{{root}}}{_CSS}</style>"


def apply_theme():
    """Inject the CSS once per run. A style-only st.html takes no layout space."""
    st.html(css())
