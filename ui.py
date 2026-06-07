"""Reusable premium UI helpers (HTML snippets) backed by theme.py styles.

These return small HTML strings (or render directly) so views can compose a more
polished, consistent look without repeating markup. All styling lives in
``theme.py``; this module only assembles it.
"""

from __future__ import annotations

import html

import streamlit as st

import icons

# A subtle skyline motif layered over each cover gradient (no external images,
# never breaks). Stretches to the cover width via preserveAspectRatio.
_SKYLINE = (
    "<svg class='rh-skyline' viewBox='0 0 320 70' preserveAspectRatio='none'>"
    "<g fill='rgba(255,255,255,0.13)'>"
    "<rect x='8' y='26' width='26' height='44'/>"
    "<rect x='38' y='12' width='18' height='58'/>"
    "<rect x='60' y='32' width='22' height='38'/>"
    "<rect x='86' y='6' width='28' height='64'/>"
    "<rect x='118' y='40' width='16' height='30'/>"
    "<rect x='138' y='20' width='30' height='50'/>"
    "<rect x='172' y='10' width='20' height='60'/>"
    "<rect x='196' y='30' width='26' height='40'/>"
    "<rect x='226' y='16' width='18' height='54'/>"
    "<rect x='248' y='24' width='30' height='46'/>"
    "<rect x='282' y='8' width='20' height='62'/>"
    "<rect x='306' y='36' width='14' height='34'/>"
    "</g>"
    "<g fill='rgba(255,255,255,0.10)'>"
    "<rect x='92' y='14' width='4' height='4'/><rect x='100' y='14' width='4' height='4'/>"
    "<rect x='92' y='24' width='4' height='4'/><rect x='100' y='24' width='4' height='4'/>"
    "<rect x='176' y='18' width='3' height='4'/><rect x='183' y='18' width='3' height='4'/>"
    "<rect x='176' y='28' width='3' height='4'/><rect x='183' y='28' width='3' height='4'/>"
    "<rect x='44' y='20' width='3' height='4'/><rect x='50' y='20' width='3' height='4'/>"
    "</g></svg>"
)

# Muted, premium cover gradients chosen deterministically per property.
_COVERS = [
    "linear-gradient(135deg,#5E6B4D,#3f4a34)",   # olive
    "linear-gradient(135deg,#3E6F63,#264c43)",   # teal
    "linear-gradient(135deg,#4A5568,#2d3340)",   # slate
    "linear-gradient(135deg,#B5713F,#7d4a26)",   # clay
    "linear-gradient(135deg,#566080,#363c54)",   # indigo
    "linear-gradient(135deg,#6E5A78,#43354c)",   # plum
]

_BADGE_TONES = {"green", "amber", "red", "gray", "olive"}


def badge(text: str, tone: str = "gray") -> str:
    """Return a pill badge as an HTML string. tone ∈ green/amber/red/gray/olive."""
    tone = tone if tone in _BADGE_TONES else "gray"
    return f"<span class='rh-badge {tone}'>{html.escape(str(text))}</span>"


def stat_card(label: str, value: str, sub: str | None = None,
              accent: bool = False) -> str:
    """Return a stat card as an HTML string (drop into a column with st.markdown)."""
    sub_html = f"<div class='rh-stat-sub'>{html.escape(sub)}</div>" if sub else ""
    cls = "rh-stat accent" if accent else "rh-stat"
    return (
        f"<div class='{cls}'>"
        f"<div class='rh-stat-label'>{html.escape(label)}</div>"
        f"<div class='rh-stat-value'>{html.escape(str(value))}</div>"
        f"{sub_html}</div>"
    )


def stat_row(cards: list[str]) -> None:
    """Render a row of pre-built stat-card HTML strings in equal columns."""
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        col.markdown(card, unsafe_allow_html=True)


def section(title: str, sub: str | None = None) -> None:
    """Render a section header with an optional right-aligned subtitle."""
    sub_html = f"<span class='rh-sec-sub'>{html.escape(sub)}</span>" if sub else ""
    st.markdown(
        f"<div class='rh-section'><h3>{html.escape(title)}</h3>{sub_html}</div>",
        unsafe_allow_html=True,
    )


# Map a domain status to a badge tone, then render the badge HTML.
_STATUS_TONE = {
    "Paid": "green", "Collected": "green", "Resolved": "green", "Closed": "green",
    "Partial": "amber", "Upcoming": "gray", "In Progress": "amber",
    "Acknowledged": "amber", "Open": "amber", "Submitted": "amber",
    "Overdue": "red", "Emergency": "red", "High": "red",
    "Med": "amber", "Low": "gray", "No charge": "gray",
}


def status_badge(status: str) -> str:
    """Return a status pill HTML string with a sensible tone for the status."""
    return badge(status, _STATUS_TONE.get(status, "gray"))


def property_card(name: str, city: str, address: str, units: int,
                  occupied: int, occupancy: float, rent_roll: str) -> str:
    """Return a premium property card (HTML string) for the Properties grid."""
    cover = _COVERS[sum(ord(c) for c in name) % len(_COVERS)]
    pct = round(occupancy * 100)
    tone = "green" if pct >= 90 else ("amber" if pct >= 50 else "red")
    e = html.escape
    return (
        f"<div class='rh-pcard'>"
        f"<div class='rh-pcard-cover' style='background:{cover}'>{_SKYLINE}"
        f"<span class='rh-pcard-ico'>{icons.svg('building', 22)}</span>"
        f"<span class='rh-pcard-city'>{e(city)}</span></div>"
        f"<div class='rh-pcard-body'>"
        f"<div class='rh-pcard-head'>"
        f"<div><div class='rh-pcard-name'>{e(name)}</div>"
        f"<div class='rh-pcard-addr'>{e(address)}</div></div>"
        f"{badge(f'{pct}% occupied', tone)}</div>"
        f"<div class='rh-pcard-stats'>"
        f"<div class='rh-pcard-stat'><div class='v'>{units}</div><div class='l'>Units</div></div>"
        f"<div class='rh-pcard-stat'><div class='v'>{occupied}</div><div class='l'>Occupied</div></div>"
        f"<div class='rh-pcard-stat'><div class='v'>{e(rent_roll)}</div><div class='l'>Rent roll</div></div>"
        f"</div></div></div>"
    )


def announcement_card(body: str, scope: str | None = None,
                      meta: str | None = None) -> None:
    """Render an on-brand announcement card (replaces the default blue st.info)."""
    scope_html = (
        f"<div class='rh-ann-scope'>{html.escape(scope)}</div>" if scope else ""
    )
    meta_html = f"<div class='rh-ann-meta'>{html.escape(meta)}</div>" if meta else ""
    st.markdown(
        f"<div class='rh-ann'>{scope_html}"
        f"<div class='rh-ann-body'>{html.escape(body)}</div>{meta_html}</div>",
        unsafe_allow_html=True,
    )
