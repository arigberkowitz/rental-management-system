"""Inline SVG icons (Lucide-style stroke icons) for HTML-rendered components.

Emoji read as cheap; these are crisp, monochrome, and inherit color via
``currentColor`` so they sit cleanly inside badges, tiles, and headers. For
Streamlit *widget* labels (buttons, nav, expanders) use the native
``:material/<name>:`` directive instead — raw HTML doesn't render there.
"""

from __future__ import annotations

# Inner SVG markup per icon (24x24 viewBox, stroke = currentColor).
_PATHS = {
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "card": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/>',
    "megaphone": '<path d="m3 11 16-5v12L3 13z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "building": '<path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M9 7h.01M9 11h.01M9 15h.01M15 7h.01M15 11h.01M15 15h.01"/>',
    "chart": '<path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6" rx="1"/><rect x="12" y="7" width="3" height="10" rx="1"/><rect x="17" y="13" width="3" height="4" rx="1"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "receipt": '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1z"/><path d="M8 7h8M8 11h8M8 15h5"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 5-5"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 9v5"/><path d="M12 17.5h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "sparkle": '<path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18"/>',
}


def svg(name: str, size: int = 18, stroke: float = 1.9) -> str:
    """Return an inline <svg> string for ``name`` (empty string if unknown)."""
    inner = _PATHS.get(name)
    if not inner:
        return ""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round" style="display:inline-block;vertical-align:-0.18em">'
        f"{inner}</svg>"
    )
