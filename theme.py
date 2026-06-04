"""Global look-and-feel: olive-green / light-gray resident-portal styling.

Injected once per page load. Keeps all CSS in one place so the visual theme is
easy to tweak without touching view logic.
"""

from __future__ import annotations

import streamlit as st

PRIMARY = "#6A7459"        # muted olive green (Pay Now button)
PRIMARY_DARK = "#565E47"
APP_BG = "#F4F4F2"
CARD_BORDER = "#EAEAE6"
LINK = "#1A73E8"

_CSS = f"""
<style>
/* ---- App canvas ---- */
.stApp {{ background-color: {APP_BG}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1080px; }}

h1, h2, h3 {{ color: #2B2B2B; font-weight: 700; letter-spacing: -0.01em; }}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {{
    background-color: #FFFFFF;
    border-right: 1px solid {CARD_BORDER};
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.4rem; }}

/* ---- Bordered containers become soft white cards ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: #FFFFFF;
    border: 1px solid {CARD_BORDER} !important;
    border-radius: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}}

/* ---- Buttons ---- */
.stButton > button {{
    border-radius: 999px;
    border: 1px solid {CARD_BORDER};
    font-weight: 600;
    padding: 0.5rem 1.3rem;
    transition: all .12s ease;
}}
.stButton > button:hover {{ border-color: {PRIMARY}; color: {PRIMARY}; }}
.stButton > button[kind="primary"],
.stButton > button[kind="primaryFormSubmit"] {{
    background-color: {PRIMARY};
    color: #FFFFFF;
    border: 1px solid {PRIMARY};
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="primaryFormSubmit"]:hover {{
    background-color: {PRIMARY_DARK};
    border-color: {PRIMARY_DARK};
    color: #FFFFFF;
}}

/* ---- Sidebar nav (radio styled as a menu) ---- */
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 2px; }}
[data-testid="stSidebar"] [role="radiogroup"] > label {{
    display: flex; align-items: center;
    padding: 11px 14px;
    border-radius: 10px;
    border-left: 3px solid transparent;
    cursor: pointer;
    color: #4A4A4A;
    font-size: 1rem;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label:hover {{ background: {APP_BG}; }}
/* hide the round radio control, keep the label text */
[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {{ display: none; }}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {{
    background: #EEF1E9;
    border-left: 3px solid {PRIMARY};
    color: #2B2B2B;
    font-weight: 700;
}}

/* ---- Resident-portal header (title + bell/gear) ---- */
.rp-header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 6px; }}
.rp-header .rp-title {{ font-size: 2rem; font-weight: 700; }}
.rp-header .rp-icons {{ display:flex; gap:14px; font-size:1.25rem; color:#6b6b6b; }}

/* ---- Credit / balance hero ---- */
.rp-balance-label {{ color:#6b6b6b; font-size:0.95rem; margin-bottom:2px; }}
.rp-balance-amount {{ font-size:2.6rem; font-weight:700; color:#2B2B2B; line-height:1.1; }}
.rp-muted {{ color:#6b6b6b; }}
.rp-link {{ color:{LINK}; font-weight:600; text-decoration:none; }}
.rp-dot-off {{ color:#E4572E; }}
.rp-dot-on {{ color:#3FA34D; }}

/* ---- Quick-link circular tiles ---- */
.rp-circle {{
    width:64px; height:64px; border-radius:50%;
    background:#F1F1EE; border:1px solid {CARD_BORDER};
    display:flex; align-items:center; justify-content:center;
    font-size:26px; margin:0 auto 6px auto;
}}
.rp-circle-label {{ text-align:center; font-size:0.86rem; color:#3a3a3a; line-height:1.2; }}

/* sidebar brand block */
.rp-brand {{ font-weight:800; letter-spacing:0.06em; line-height:1.15; color:#2B2B2B; }}
.rp-unit {{ color:#6b6b6b; font-size:0.85rem; margin-top:2px; }}

/* tighten metric cards */
[data-testid="stMetric"] {{ background:#FFFFFF; border:1px solid {CARD_BORDER};
    border-radius:14px; padding:14px 16px; }}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
