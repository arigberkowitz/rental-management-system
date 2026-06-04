"""Authentication & role-based access control.

v1 validates submitted credentials against the seeded users table. Passwords
are stored as bcrypt hashes (never plaintext), even for the demo accounts.
"""

from __future__ import annotations

import bcrypt
import streamlit as st

import db

MANAGER = "MANAGER"
RENTER = "RENTER"


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plaintext: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate(username: str, password: str):
    """Return the user row on success, else None."""
    row = db.query_one(
        "SELECT * FROM users WHERE username = ? AND status = 'active'",
        (username.strip().lower(),),
    )
    if row and verify_password(password, row["password_hash"]):
        return row
    return None


# --- Session helpers ---------------------------------------------------------

def login(user_row) -> None:
    st.session_state.user = {
        "id": user_row["id"],
        "username": user_row["username"],
        "name": user_row["name"],
        "role": user_row["role"],
    }


def logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def current_user():
    return st.session_state.get("user")


def require_role(*roles: str) -> None:
    """Server-side guard: stop rendering if the user lacks the role.

    Every portal view calls this so authorization is enforced on the data path,
    not merely by hiding sidebar links.
    """
    user = current_user()
    if not user:
        st.error("Please log in.")
        st.stop()
    if roles and user["role"] not in roles:
        st.error("You don't have permission to view this page.")
        st.stop()
