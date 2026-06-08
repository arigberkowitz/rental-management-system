"""Property cover-photo helpers.

Turns an uploaded image file into a small base64 data URI so it can be embedded
directly in the HTML property cards. Thumbnails are cached (keyed by path +
mtime) so we don't re-encode on every rerun. Any failure returns None and the
card falls back to its gradient cover.
"""

from __future__ import annotations

import base64
import io
import os

import streamlit as st


@st.cache_data(show_spinner=False)
def _encode(path: str, mtime: float, max_w: int = 700) -> str | None:
    try:
        from PIL import Image

        img = Image.open(path).convert("RGB")
        w, h = img.size
        if w > max_w:
            img = img.resize((max_w, max(1, int(h * max_w / w))))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


def cover_uri(path: str | None) -> str | None:
    """Data URI for a cover image path, or None if missing/unreadable."""
    if not path or not os.path.exists(path):
        return None
    try:
        return _encode(path, os.path.getmtime(path))
    except Exception:
        return None
