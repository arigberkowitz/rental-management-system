"""Rental Management System — Streamlit entry point.

A single login screen routes users to the Manager or Renter portal based on
their role (RBAC). Authorization is enforced server-side in each view, not just
by hiding sidebar links.
"""

from __future__ import annotations

import streamlit as st

import auth
import db
import hero
import icons
import repo
import theme
from views import manager, renter

st.set_page_config(page_title="RentHarbor", page_icon=":material/cottage:",
                   layout="wide", initial_sidebar_state="expanded")
theme.inject()

APP_NAME = "RENTHARBOR"

RENTER_ICONS = {
    "Home": ":material/home:", "Pay Rent": ":material/credit_card:",
    "Maintenance": ":material/build:",
    "Documents & Profile": ":material/description:",
    "Announcements": ":material/campaign:",
}
MANAGER_ICONS = {
    "Dashboard": ":material/dashboard:", "Properties & Units": ":material/apartment:",
    "Tenants & Leases": ":material/group:", "Rent & Payments": ":material/payments:",
    "Maintenance": ":material/build:", "Reports": ":material/bar_chart:",
    "Announcements": ":material/campaign:",
}


@st.cache_resource
def _bootstrap():
    """Initialize the schema and seed demo data on first run."""
    db.init_db()
    if not db.is_seeded():
        import seed
        seed.seed()
    return True


_bootstrap()


def login_screen() -> None:
    hero.render_login_hero()
    st.markdown(
        "<p style='text-align:center;color:#6B7167;margin:22px 0 6px;font-size:1.02rem'>"
        "Sign in to your portal</p>",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.container(border=True):
            with st.form("login"):
                st.subheader("Log in")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", type="primary",
                                         use_container_width=True):
                    user = auth.authenticate(username, password)
                    if user:
                        auth.login(user)
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with st.expander("Demo accounts"):
            st.markdown(
                """
| Username | Password | Role |
|---|---|---|
| `ari` | `manager123` | Manager |
| `zach` | `owner123` | Manager (owner) |
| `rosa` | `tenant123` | Renter |
| `marcus` | `tenant123` | Renter |
| `linh` | `tenant123` | Renter |
"""
            )


def _sidebar_brand(user, is_manager) -> None:
    mark = f"<span class='rh-brand-ico'>{icons.svg('home', 18)}</span>"
    if is_manager:
        st.markdown(
            f"<div class='rh-brand-mark'>{mark}"
            f"<span class='rp-brand'>{APP_NAME}</span></div>"
            "<div class='rp-unit'>Property Management</div>",
            unsafe_allow_html=True,
        )
    else:
        lease = repo.active_lease_for_tenant(user["id"])
        prop = (lease["property_name"] if lease else APP_NAME).upper()
        unit = f"Unit {lease['unit_label']} · {lease['city']}" if lease else ""
        st.markdown(
            f"<div class='rh-brand-mark'>{mark}"
            f"<span class='rp-unit' style='letter-spacing:.12em'>{APP_NAME}</span></div>"
            f"<div class='rp-brand' style='font-size:1.25rem'>{prop}</div>"
            f"<div class='rp-unit'>{unit}</div>",
            unsafe_allow_html=True,
        )
    st.divider()


def portal() -> None:
    user = auth.current_user()
    is_manager = user["role"] == auth.MANAGER
    sections = manager.SECTIONS if is_manager else renter.SECTIONS
    icons = MANAGER_ICONS if is_manager else RENTER_ICONS

    with st.sidebar:
        _sidebar_brand(user, is_manager)
        section = st.radio(
            "Navigate", sections, key="nav", label_visibility="collapsed",
            format_func=lambda s: f"{icons.get(s, '•')} {s}",
        )
        st.divider()
        st.caption(f"Signed in as **{user['name']}** · {user['role'].title()}")
        if st.button("Log out", use_container_width=True):
            auth.logout()
            st.rerun()

    if is_manager:
        manager.render(user, section)
    else:
        renter.render(user, section)


if auth.current_user():
    portal()
else:
    login_screen()
