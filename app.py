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
import session
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
    "Announcements": ":material/campaign:", "Settings": ":material/settings:",
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

# Apply any due late fees once per session (guarded — never breaks the app).
if "_late_fee_checked" not in st.session_state:
    try:
        repo.apply_late_fees()
    except Exception:
        pass
    st.session_state["_late_fee_checked"] = True


_LOGIN_HERO = """
<style>
.rh-lhero{position:relative;margin:-1rem 0 1.5rem;padding:0 0 0.5rem;text-align:center;overflow:hidden}
.rh-lhero::before{content:'';position:absolute;top:-60%;left:50%;transform:translateX(-50%);
  width:60rem;height:60rem;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle at 50% 40%, rgba(94,107,77,0.12), rgba(94,107,77,0.03) 50%, transparent 72%)}
.rh-lnav{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;
  max-width:1040px;margin:0 auto;padding:14px 8px 18px;border-bottom:1px dashed #E7E7E0}
.rh-lbrand{display:flex;align-items:center;gap:9px;font-family:'Plus Jakarta Sans',sans-serif;
  font-weight:800;font-size:18px;letter-spacing:-0.02em;color:#1E231D}
.rh-lmk{width:28px;height:28px;border-radius:8px;background:#5E6B4D;color:#fff;display:flex;
  align-items:center;justify-content:center;font-size:14px}
.rh-lmenu{display:flex;gap:26px;font-size:14px;color:#6B7167}
.rh-lbody{position:relative;z-index:1;padding:46px 16px 8px}
.rh-lpill{display:inline-block;font-size:12.5px;font-weight:600;color:#4A5540;background:#EDF1E6;
  border:1px solid #DDE4D0;border-radius:999px;padding:6px 14px;margin-bottom:20px}
.rh-lhero h1{font-family:'Plus Jakarta Sans',sans-serif;font-size:46px;line-height:1.05;font-weight:800;
  letter-spacing:-0.03em;color:#1E231D;margin:0 auto;max-width:16ch}
.rh-lhero p{font-size:18px;color:#6B7167;max-width:48ch;margin:18px auto 4px;line-height:1.5}
.rh-lcloud{text-align:center;margin:30px auto 4px;padding-top:24px;border-top:1px solid #E7E7E0;max-width:880px}
.rh-lcloud-h{font-size:14px;color:#6B7167;font-weight:600}
.rh-llogos{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:24px 40px;margin-top:22px}
.rh-llogos span{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:17px;
  color:#A9ADA2;letter-spacing:-0.02em}
@media(max-width:760px){.rh-lmenu{display:none}.rh-lhero h1{font-size:34px}.rh-lhero p{font-size:16px}}
</style>
<div class="rh-lhero">
  <div class="rh-lnav">
    <div class="rh-lbrand"><span class="rh-lmk">&#8962;</span> RentHarbor</div>
    <div class="rh-lmenu"><span>Properties</span><span>Tenants</span><span>Pricing</span><span>About</span></div>
  </div>
  <div class="rh-lbody">
    <span class="rh-lpill">New &middot; Automated Late Fees &amp; Rent Reminders</span>
    <h1>Property Management, on autopilot</h1>
    <p>Rent roll, payments, maintenance, and leases &mdash; every property in one calm dashboard. Sign in to your portal below.</p>
  </div>
</div>
"""

_LOGIN_CLOUD = """
<div class="rh-lcloud">
  <div class="rh-lcloud-h">Trusted by Independent Landlords and Property Teams</div>
  <div class="rh-llogos">
    <span>Sausalito Living</span><span>BayHaus</span><span>Marin Realty</span>
    <span>OakField</span><span>Harbor Co.</span>
  </div>
</div>
"""


def login_screen() -> None:
    st.markdown(_LOGIN_HERO, unsafe_allow_html=True)
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
                        session.issue(user)  # remember across reloads (guarded)
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

    st.markdown(_LOGIN_CLOUD, unsafe_allow_html=True)


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
            session.clear()  # drop the persistent cookie too
            auth.logout()
            st.rerun()

    if is_manager:
        manager.render(user, section)
    else:
        renter.render(user, section)


# Restore a signed-in user from the persistent cookie (guarded; no-op if none).
if not auth.current_user():
    _restored = session.restore()
    if _restored:
        st.session_state["user"] = _restored

if auth.current_user():
    portal()
else:
    login_screen()
