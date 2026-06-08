"""Email notifications via Resend — a safe no-op until configured.

Sends transactional emails (payment receipts, maintenance updates, rent
reminders) only when BOTH are true:
  * a Resend API key is available (``st.secrets["RESEND_API_KEY"]`` or the
    ``RESEND_API_KEY`` env var), and
  * the manager has turned notifications on (``app_prefs`` toggle).

If either is missing, every send is a silent no-op, so the app behaves exactly
as before until you opt in. Nothing here ever raises into the UI.
"""

from __future__ import annotations

import os

import db

ENABLED_PREF = "notifications_enabled"   # "1" on / "0" off (default off)
API_URL = "https://api.resend.com/emails"


def _secret(name: str) -> str | None:
    val = os.environ.get(name)
    if val:
        return val
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return None


def _api_key() -> str | None:
    return _secret("RESEND_API_KEY")


def _sender() -> str:
    return _secret("EMAIL_FROM") or "RentHarbor <onboarding@resend.dev>"


def is_configured() -> bool:
    """True if a Resend key is present (regardless of the on/off toggle)."""
    return bool(_api_key())


def enabled() -> bool:
    return db.get_pref(ENABLED_PREF, "0") == "1"


def set_enabled(on: bool) -> None:
    db.set_pref(ENABLED_PREF, "1" if on else "0")


def can_send() -> bool:
    return is_configured() and enabled()


def send_email(to: str | None, subject: str, html: str) -> bool:
    """Send one email. Returns True on success, False (silently) otherwise."""
    if not to or not can_send():
        return False
    try:
        import requests

        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {_api_key()}",
                     "Content-Type": "application/json"},
            json={"from": _sender(), "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Message builders (kept simple + on-brand)
# --------------------------------------------------------------------------- #

def _shell(title: str, body_html: str) -> str:
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:520px;margin:auto;"
        "border:1px solid #E7E7E0;border-radius:14px;overflow:hidden'>"
        "<div style='background:#5E6B4D;color:#fff;padding:16px 20px;font-weight:700;"
        "font-size:18px'>RentHarbor</div>"
        f"<div style='padding:20px 22px;color:#1E231D;line-height:1.6'>"
        f"<h2 style='margin:0 0 12px;font-size:18px'>{title}</h2>{body_html}</div>"
        "<div style='padding:12px 22px;color:#6B7167;font-size:12px;border-top:1px solid #E7E7E0'>"
        "This is an automated message from your RentHarbor property portal.</div></div>"
    )


def payment_receipt(to: str, name: str, amount_str: str, property_unit: str,
                    method: str, ref: str | None = None) -> bool:
    body = (
        f"<p>Hi {name},</p>"
        f"<p>We've received your payment of <strong>{amount_str}</strong> for "
        f"{property_unit} via {method}.</p>"
        + (f"<p style='color:#6B7167;font-size:13px'>Reference: {ref}</p>" if ref else "")
        + "<p>Thank you!</p>"
    )
    return send_email(to, f"Payment received — {amount_str}", _shell("Payment receipt", body))


def ticket_status_email(to: str, name: str, title: str, status: str,
                        property_unit: str) -> bool:
    body = (
        f"<p>Hi {name},</p>"
        f"<p>Your maintenance request <strong>{title}</strong> for {property_unit} "
        f"is now <strong>{status}</strong>.</p>"
        "<p>We'll keep you posted on any further updates.</p>"
    )
    return send_email(to, f"Maintenance update — {status}",
                      _shell("Maintenance update", body))


def rent_reminder(to: str, name: str, balance_str: str, due_str: str,
                  property_unit: str) -> bool:
    body = (
        f"<p>Hi {name},</p>"
        f"<p>This is a friendly reminder that your balance of "
        f"<strong>{balance_str}</strong> for {property_unit} is due {due_str}.</p>"
        "<p>You can pay anytime from your RentHarbor portal.</p>"
    )
    return send_email(to, f"Rent reminder — {balance_str} due",
                      _shell("Rent reminder", body))
