"""Local file storage for uploads (maintenance photos, lease PDFs).

For the demo, files are written under ``uploads/``. On Streamlit Community Cloud
the filesystem is ephemeral (same caveat as the SQLite DB) -- swap for object
storage when moving to a durable backend.
"""

from __future__ import annotations

import os
import uuid

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")


def save_upload(uploaded_file, subdir: str = "") -> tuple[str, str]:
    """Persist a Streamlit UploadedFile; return (path, original_filename)."""
    target_dir = os.path.join(UPLOAD_DIR, subdir) if subdir else UPLOAD_DIR
    os.makedirs(target_dir, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1]
    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(target_dir, safe_name)
    with open(path, "wb") as fh:
        fh.write(uploaded_file.getbuffer())
    return path, uploaded_file.name
