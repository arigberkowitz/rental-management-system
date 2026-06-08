"""Persistent login across page reloads, via a browser cookie.

Streamlit keeps auth only in ``st.session_state``, which is wiped on a full page
reload — so refreshing logs users out. This module stores a random session token
in a cookie and maps it (server-side, in ``app_prefs``) to a user id, so a reload
can restore the session.

Every operation is wrapped in try/except: if the cookie component is unavailable
or anything fails, we silently fall back to normal session-only login. So this
feature is purely additive and can never break the login flow.
"""

from __future__ import annotations

import secrets as _secrets

import db

COOKIE_NAME = "rh_session"
_PREF_PREFIX = "session:"


def _controller():
    try:
        from streamlit_cookies_controller import CookieController

        return CookieController()
    except Exception:
        return None


def issue(user) -> None:
    """Create a server-side token for the user and set it as a cookie."""
    try:
        token = _secrets.token_urlsafe(24)
        db.set_pref(f"{_PREF_PREFIX}{token}", str(user["id"]))
        ctrl = _controller()
        if ctrl is not None:
            ctrl.set(COOKIE_NAME, token, max_age=60 * 60 * 24 * 30)  # 30 days
    except Exception:
        pass


def restore():
    """Return a user dict from the cookie token, or None."""
    try:
        ctrl = _controller()
        if ctrl is None:
            return None
        token = ctrl.get(COOKIE_NAME)
        if not token:
            return None
        uid = db.get_pref(f"{_PREF_PREFIX}{token}")
        if not uid:
            return None
        import repo

        row = repo.get_user(int(uid))
        if row and row["status"] == "active":
            return {
                "id": row["id"], "username": row["username"],
                "name": row["name"], "role": row["role"],
            }
    except Exception:
        return None
    return None


def clear() -> None:
    """Invalidate the server-side token and remove the cookie."""
    try:
        ctrl = _controller()
        if ctrl is None:
            return
        token = ctrl.get(COOKIE_NAME)
        if token:
            db.set_pref(f"{_PREF_PREFIX}{token}", "")  # invalidate server-side
        try:
            ctrl.remove(COOKIE_NAME)
        except Exception:
            ctrl.set(COOKIE_NAME, "", max_age=0)
    except Exception:
        pass
