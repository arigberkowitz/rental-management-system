"""Reusable premium UI helpers (HTML snippets) backed by theme.py styles.

These return small HTML strings (or render directly) so views can compose a more
polished, consistent look without repeating markup. All styling lives in
``theme.py``; this module only assembles it.
"""

from __future__ import annotations

import html

import streamlit as st

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
