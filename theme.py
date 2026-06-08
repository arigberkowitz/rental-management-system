"""Global look-and-feel — a premium, calm property-management aesthetic.

Injected once per page load. All visual styling lives here so the theme is easy
to tune without touching view logic. Class names used by the views (``rp-*``)
are preserved and enhanced; new helpers (``rh-*``) back the upgraded components
in ``ui.py``.
"""

from __future__ import annotations

import streamlit as st

# ---- Brand palette -------------------------------------------------------- #
PRIMARY = "#5E6B4D"        # deep olive
PRIMARY_DARK = "#4A5540"
PRIMARY_SOFT = "#EDF1E6"   # olive tint for fills / active states
ACCENT = "#C2703D"         # warm clay, used sparingly for highlights
INK = "#1E231D"            # near-black text
MUTED = "#6B7167"          # secondary text
APP_BG = "#F6F6F2"         # warm paper background
SURFACE = "#FFFFFF"
CARD_BORDER = "#E7E7E0"
LINK = "#2F6F4E"
GREEN = "#2E7D55"
AMBER = "#B9821B"
RED = "#C0492F"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

/* ---- Global type + canvas ---- */
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stSidebar"], input, textarea, select, button {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
.stApp {{ background-color: {APP_BG}; color: {INK}; }}
.block-container {{ padding-top: 2.0rem; padding-bottom: 4rem; max-width: 1140px; }}

h1, h2, h3, h4 {{
    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    color: {INK};
    font-weight: 700;
    letter-spacing: -0.02em;
}}
h1 {{ font-size: 2.1rem; }}
h2 {{ font-size: 1.5rem; }}
h3 {{ font-size: 1.2rem; }}
p, span, label, li, .stMarkdown {{ color: {INK}; }}
a, .rp-link {{ color: {LINK}; font-weight: 600; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
hr {{ border-color: {CARD_BORDER}; }}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {{
    background-color: {SURFACE};
    border-right: 1px solid {CARD_BORDER};
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.4rem; }}

/* ---- Bordered containers become soft cards ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {SURFACE};
    border: 1px solid {CARD_BORDER} !important;
    border-radius: 18px;
    box-shadow: 0 1px 2px rgba(30,35,29,0.04), 0 10px 30px rgba(30,35,29,0.045);
    transition: box-shadow .18s ease, transform .18s ease;
}}

/* ---- Buttons ---- */
.stButton > button, .stDownloadButton > button {{
    border-radius: 999px;
    border: 1px solid {CARD_BORDER};
    font-weight: 600;
    padding: 0.52rem 1.35rem;
    color: {INK};
    background: {SURFACE};
    transition: all .14s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: {PRIMARY}; color: {PRIMARY};
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(94,107,77,0.16);
}}
.stButton > button[kind="primary"],
.stButton > button[kind="primaryFormSubmit"] {{
    background: {PRIMARY}; color: #FFFFFF; border: 1px solid {PRIMARY};
    box-shadow: 0 4px 14px rgba(94,107,77,0.22);
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="primaryFormSubmit"]:hover {{
    background: {PRIMARY_DARK}; border-color: {PRIMARY_DARK}; color: #FFFFFF;
}}

/* ---- Inputs ---- */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {{
    border-radius: 12px !important;
}}
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
    border-radius: 12px;
}}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 3px {PRIMARY_SOFT} !important;
}}

/* ---- Tabs (spaced out so each label reads as its own thing) ---- */
.stTabs [data-baseweb="tab-list"] {{ gap: 34px; border-bottom: 1px solid {CARD_BORDER}; }}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0; font-weight: 600; color: {MUTED};
    padding: 10px 4px; font-size: 1rem;
}}
.stTabs [data-baseweb="tab"]:hover {{ color: {INK}; }}
.stTabs [aria-selected="true"] {{ color: {PRIMARY}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {PRIMARY}; height: 3px; }}

/* ---- Clickable property card -------------------------------------------- #
   Each card lives in a keyed container (class st-key-pcard_<id>). The button is
   a NORMAL in-flow element given a real height — so its clickable area is
   guaranteed by layout (no absolute-coverage guessing). The card visual is laid
   absolutely on TOP of the button and made click-through, so a click anywhere on
   the card hits the button. In-session rerun, so login is preserved. --------- */
[class*="st-key-pcard_"] {{ position: relative; }}
/* The visual card sits on top, but ignores clicks (they pass to the button).
   Target the container that actually holds the card via :has, and also any
   first-child fallback, so the card is always click-through and on top. */
[class*="st-key-pcard_"] [data-testid="stElementContainer"]:has(.rh-pcard),
[class*="st-key-pcard_"] [data-testid="stElementContainer"]:first-child {{
    position: absolute; top: 0; left: 0; right: 0; z-index: 2; pointer-events: none;
}}
[class*="st-key-pcard_"] .rh-pcard {{ margin-bottom: 0; pointer-events: none; }}
/* The button is the real clickable area: full width, card-height, invisible. */
[class*="st-key-pcard_"] [data-testid="stButton"] {{ margin: 0; }}
[class*="st-key-pcard_"] [data-testid="stButton"] > button {{
    width: 100%; min-height: 268px; height: 268px;
    opacity: 0; border: none; background: transparent; cursor: pointer;
}}
/* keep the card's hover lift */
[class*="st-key-pcard_"]:hover .rh-pcard {{
    transform: translateY(-2px); box-shadow: 0 12px 30px rgba(30,35,29,0.10);
}}

/* ---- Metric cards ---- */
[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {CARD_BORDER};
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(30,35,29,0.04);
}}
[data-testid="stMetricLabel"] {{
    color: {MUTED}; font-size: 0.82rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em;
}}
[data-testid="stMetricValue"] {{
    font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; color: {INK};
}}

/* ---- Sidebar nav (radio styled as a menu) ---- */
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 2px; }}
[data-testid="stSidebar"] [role="radiogroup"] > label {{
    display: flex; align-items: center;
    padding: 11px 14px; border-radius: 12px;
    border-left: 3px solid transparent; cursor: pointer;
    color: {MUTED}; font-size: 0.98rem; font-weight: 500;
    transition: background .12s ease, color .12s ease;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label:hover {{ background: {APP_BG}; color: {INK}; }}
[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {{ display: none; }}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {{
    background: {PRIMARY_SOFT};
    border-left: 3px solid {PRIMARY};
    color: {PRIMARY_DARK}; font-weight: 700;
}}

/* ---- Resident-portal header (title + bell/gear) ---- */
.rp-header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 10px; }}
.rp-header .rp-title {{ font-family:'Plus Jakarta Sans',sans-serif; font-size: 2rem; font-weight: 700; letter-spacing:-0.02em; }}
.rp-header .rp-icons {{ display:flex; gap:14px; font-size:1.2rem; color:{MUTED}; }}

/* ---- Credit / balance hero ---- */
.rp-balance-label {{ color:#dfe6d4; font-size:0.9rem; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:4px; }}
.rp-balance-amount {{ font-family:'Plus Jakarta Sans',sans-serif; font-size:3rem; font-weight:800; color:#FFFFFF; line-height:1.05; }}
.rp-muted {{ color:{MUTED}; }}
.rp-link {{ color:{LINK}; font-weight:600; text-decoration:none; }}
.rp-dot-off {{ color:{RED}; }}
.rp-dot-on {{ color:{GREEN}; }}

/* ---- Quick-link circular tiles ---- */
.rp-circle {{
    width:60px; height:60px; border-radius:18px;
    background:{PRIMARY_SOFT}; border:1px solid {CARD_BORDER};
    display:flex; align-items:center; justify-content:center;
    font-size:24px; margin:0 auto 8px auto;
    transition: transform .14s ease, box-shadow .14s ease;
}}
.rp-circle:hover {{ transform: translateY(-2px); box-shadow: 0 6px 16px rgba(94,107,77,0.16); }}
.rp-circle-label {{ text-align:center; font-size:0.86rem; color:#3a3a3a; line-height:1.2; }}

/* sidebar brand block */
.rp-brand {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; letter-spacing:0.04em; line-height:1.15; color:{INK}; }}
.rp-unit {{ color:{MUTED}; font-size:0.85rem; margin-top:2px; }}
.rh-brand-mark {{ display:flex; align-items:center; gap:11px; margin-bottom:4px; }}
.rh-brand-ico {{
    width:36px; height:36px; border-radius:11px; flex:none;
    background:{PRIMARY}; color:#fff;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 4px 12px rgba(94,107,77,0.30);
}}

/* ---- Reusable premium components (ui.py) ---- */
.rh-balance {{
    background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
    border-radius: 20px; padding: 26px 28px; color:#fff;
    box-shadow: 0 12px 30px rgba(74,85,64,0.30);
}}
.rh-section {{ display:flex; align-items:baseline; justify-content:space-between; margin: 6px 0 10px; }}
.rh-section h3 {{ margin:0; }}
.rh-section .rh-sec-sub {{ color:{MUTED}; font-size:0.85rem; }}

.rh-stat {{
    background:{SURFACE}; border:1px solid {CARD_BORDER}; border-radius:16px;
    padding:16px 18px; height:100%;
}}
.rh-stat .rh-stat-label {{ color:{MUTED}; font-size:0.78rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; }}
.rh-stat .rh-stat-value {{ font-family:'Plus Jakarta Sans',sans-serif; font-size:1.8rem; font-weight:800; color:{INK}; line-height:1.15; margin-top:4px; }}
.rh-stat .rh-stat-sub {{ color:{MUTED}; font-size:0.82rem; margin-top:2px; }}
.rh-stat.accent {{ border-left:4px solid {PRIMARY}; }}

.rh-badge {{
    display:inline-flex; align-items:center; gap:6px;
    font-size:0.76rem; font-weight:700; letter-spacing:0.02em;
    padding:4px 11px; border-radius:999px; white-space:nowrap;
}}
.rh-badge::before {{ content:''; width:7px; height:7px; border-radius:50%; background:currentColor; opacity:.9; }}
.rh-badge.green {{ background:#E5F2EA; color:{GREEN}; }}
.rh-badge.amber {{ background:#FBF1DD; color:{AMBER}; }}
.rh-badge.red   {{ background:#FBE7E2; color:{RED}; }}
.rh-badge.gray  {{ background:#EEEEE9; color:{MUTED}; }}
.rh-badge.olive {{ background:{PRIMARY_SOFT}; color:{PRIMARY_DARK}; }}

.rh-row {{ display:flex; align-items:center; justify-content:space-between; gap:12px;
    padding:12px 2px; border-bottom:1px solid {CARD_BORDER}; }}
.rh-row:last-child {{ border-bottom:none; }}
.rh-row .rh-row-title {{ font-weight:600; color:{INK}; }}
.rh-row .rh-row-sub {{ color:{MUTED}; font-size:0.85rem; }}

/* Announcement card — replaces the default blue st.info for on-brand feel */
.rh-ann {{
    background:{PRIMARY_SOFT}; border:1px solid #DDE4D0;
    border-left:4px solid {PRIMARY}; border-radius:14px;
    padding:14px 16px; margin-bottom:10px;
}}
.rh-ann .rh-ann-scope {{ font-weight:700; color:{PRIMARY_DARK}; font-size:0.9rem; margin-bottom:2px; }}
.rh-ann .rh-ann-body {{ color:{INK}; line-height:1.5; }}
.rh-ann .rh-ann-meta {{ color:{MUTED}; font-size:0.78rem; margin-top:6px; }}

/* Priority stat cards (manager dashboard maintenance) */
.rh-prio {{ display:flex; gap:10px; }}
.rh-prio-card {{ flex:1; background:{SURFACE}; border:1px solid {CARD_BORDER};
    border-radius:14px; padding:12px 14px; }}
.rh-prio-card .dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; margin-bottom:9px; }}
.rh-prio-card .dot.red {{ background:{RED}; }}
.rh-prio-card .dot.amber {{ background:{AMBER}; }}
.rh-prio-card .dot.gray {{ background:{MUTED}; }}
.rh-prio-card .n {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.6rem; color:{INK}; line-height:1; }}
.rh-prio-card .l {{ color:{MUTED}; font-size:0.74rem; text-transform:uppercase; letter-spacing:0.04em; margin-top:4px; }}

/* Empty states */
.rh-empty {{ text-align:center; padding:34px 22px; }}
.rh-empty-ico {{
    width:54px; height:54px; border-radius:16px; margin:0 auto 12px;
    background:{PRIMARY_SOFT}; color:{PRIMARY};
    display:flex; align-items:center; justify-content:center;
}}
.rh-empty-title {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; font-size:1.05rem; color:{INK}; }}
.rh-empty-body {{ color:{MUTED}; font-size:0.9rem; margin-top:4px; max-width:30rem; margin-left:auto; margin-right:auto; }}

/* Property cards (manager Properties grid) */
.rh-pcard {{
    border:1px solid {CARD_BORDER}; border-radius:18px; overflow:hidden;
    background:{SURFACE}; box-shadow:0 1px 2px rgba(30,35,29,0.04), 0 10px 28px rgba(30,35,29,0.05);
    margin-bottom:14px; transition:transform .16s ease, box-shadow .16s ease;
}}
.rh-pcard:hover {{ transform:translateY(-2px); box-shadow:0 12px 30px rgba(30,35,29,0.10); }}
.rh-pcard-cover {{
    height:104px; position:relative; display:flex; align-items:flex-end;
    padding:12px 16px; color:#fff; overflow:hidden;
}}
.rh-pcard-cover .rh-skyline {{ position:absolute; left:0; bottom:0; width:100%; height:78%; }}
.rh-pcard-cover .rh-pcard-city {{ position:relative; z-index:1; font-size:0.8rem; font-weight:600; opacity:.95;
    text-transform:uppercase; letter-spacing:0.06em; }}
.rh-pcard-cover .rh-pcard-ico {{ position:absolute; z-index:1; top:12px; right:14px; opacity:.85; }}
.rh-pcard-body {{ padding:14px 16px 16px; }}
.rh-pcard-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }}
.rh-pcard-name {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; font-size:1.05rem; color:{INK}; line-height:1.2; }}
.rh-pcard-addr {{ color:{MUTED}; font-size:0.82rem; margin-top:3px; }}
.rh-pcard-stats {{ display:flex; gap:20px; margin-top:14px; padding-top:12px; border-top:1px solid {CARD_BORDER}; }}
.rh-pcard-stat .v {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; font-size:1.15rem; color:{INK}; }}
.rh-pcard-stat .l {{ color:{MUTED}; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.04em; }}

/* Status timeline chips (maintenance ticket progress) */
.rh-steps {{ display:flex; flex-wrap:wrap; gap:6px; margin:8px 0; }}
.rh-step {{
    font-size:0.75rem; font-weight:600; padding:4px 11px; border-radius:999px;
    border:1px solid {CARD_BORDER}; color:{MUTED}; background:{SURFACE};
}}
.rh-step.done {{ background:{PRIMARY_SOFT}; color:{PRIMARY_DARK}; border-color:#D7DEC9; }}
.rh-step.now  {{ background:{PRIMARY}; color:#FFFFFF; border-color:{PRIMARY}; }}

/* Sandbox / test-mode banner */
.rh-sandbox {{
    display:inline-flex; align-items:center; gap:8px;
    background:#EEF0FF; color:#3B36B8; border:1px solid #D7D9FB;
    padding:8px 14px; border-radius:999px; font-weight:600; font-size:0.86rem;
}}
.rh-sandbox::before {{ content:''; width:8px; height:8px; border-radius:50%; background:#635bff; }}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
