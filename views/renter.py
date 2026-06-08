"""Renter Portal — dashboard, mock Stripe payments, maintenance, documents."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import auth
import db
import icons
import notifications
import payments
import repo
import storage
import ui
import utils

SECTIONS = ["Home", "Pay Rent", "Maintenance", "Documents & Profile", "Announcements"]

CATEGORIES = ["plumbing", "electrical", "HVAC", "appliance", "other"]
PRIORITIES = ["Low", "Med", "High", "Emergency"]


def _go(section: str) -> None:
    """Navigate the sidebar nav radio to another section (used by quick links)."""
    st.session_state["nav"] = section


def render(user, section: str) -> None:
    auth.require_role(auth.RENTER)  # server-side guard
    lease = repo.active_lease_for_tenant(user["id"])
    if section == "Home":
        _dashboard(user, lease)
    elif section == "Pay Rent":
        _pay(user, lease)
    elif section == "Maintenance":
        _maintenance(user, lease)
    elif section == "Documents & Profile":
        _documents(user, lease)
    elif section == "Announcements":
        _announcements(user, lease)


def _no_lease():
    ui.empty_state("file", "No active lease",
                   "You don't have an active lease on file. "
                   "Please contact your property manager.")


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

def _dashboard(user, lease) -> None:
    # header row: title + bell / gear (mirrors the resident-portal layout)
    open_count = len([t for t in repo.tickets_for_tenant(user["id"])
                      if t["status"] not in ("Closed", "Resolved")]) if lease else 0
    st.markdown(
        f"""
        <div class="rp-header">
          <div class="rp-title">Home</div>
          <div class="rp-icons">{icons.svg('bell', 20)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not lease:
        _no_lease()
        return

    balance = repo.lease_balance(lease["id"])
    due = utils.due_date_for(utils.current_period(), lease["due_day"])
    autopay_key = f"autopay:{lease['id']}"
    autopay_on = db.get_pref(autopay_key, "0") == "1"

    # ---- Premium balance hero -------------------------------------------- #
    paid_up = balance <= 0
    status_pill = (
        "<span class='rh-badge green' style='background:rgba(255,255,255,.16);color:#eaf3e2'>Paid up</span>"
        if paid_up else
        "<span class='rh-badge amber' style='background:rgba(255,255,255,.16);color:#fbe6c8'>Balance due</span>"
    )
    autopay_pill = ("<span class='rh-badge' style='background:rgba(255,255,255,.16);color:#eaf3e2'>"
                    "Autopay on</span>") if autopay_on else ""
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='rh-balance' style='margin-bottom:18px'>
          <div style='display:flex;justify-content:space-between;align-items:flex-start'>
            <div>
              <div class='rp-balance-label'>Balance due</div>
              <div class='rp-balance-amount'>{utils.money_cents(max(balance, 0))}</div>
              <div style='color:#dfe6d4;margin-top:8px;font-size:0.95rem'>
                Next due {due.strftime('%b %d, %Y')} &nbsp;·&nbsp; Rent {utils.money(lease['rent_amount'])}/mo
              </div>
            </div>
            <div style='display:flex;gap:8px'>{status_pill}{autopay_pill}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    act_l, act_r = st.columns([1, 1])
    with act_l:
        st.button("Pay now", type="primary", use_container_width=True,
                  on_click=_go, args=("Pay Rent",), disabled=paid_up)
    with act_r:
        new_autopay = st.toggle(
            "Autopay on the due date", value=autopay_on,
            help="Automatically pay your full balance each month on the due date. "
                 "(Demo — no real charge is made.)",
        )
        if new_autopay != autopay_on:
            db.set_pref(autopay_key, "1" if new_autopay else "0")
            st.rerun()
    if autopay_on and not paid_up:
        st.caption(f"Autopay is on — your balance will be paid automatically on "
                   f"{due.strftime('%b %d')}.")

    # ---- Quick links (rounded tiles) ------------------------------------- #
    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    ui.section("Quick Links")
    links = [
        ("card", "Pay Rent", "Pay Rent"),
        ("wrench", "Submit Request", "Maintenance"),
        ("file", "View Documents", "Documents & Profile"),
        ("megaphone", "Announcements", "Announcements"),
        ("shield", "Renter's Insurance", None),
    ]
    cols = st.columns(len(links))
    for col, (icon, label, target) in zip(cols, links):
        with col:
            st.markdown(f"<div class='rp-circle'>{icons.svg(icon, 24)}</div>",
                        unsafe_allow_html=True)
            if target:
                st.button(label, key=f"ql_{label}", use_container_width=True,
                          on_click=_go, args=(target,))
            else:
                st.button(label, key=f"ql_{label}", use_container_width=True,
                          help="Available in Phase 2")

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("#### Your Lease")
            for label, value in [
                ("Property", lease["property_name"]),
                ("Unit", f"{lease['unit_label']} ({lease['city']})"),
                ("Rent", f"{utils.money(lease['rent_amount'])} / month"),
                ("Due day", f"{lease['due_day']} of each month"),
                ("Lease ends", lease["end_date"]),
            ]:
                st.markdown(
                    f"<div class='rh-row'><span class='rh-row-sub'>{label}</span>"
                    f"<span class='rh-row-title'>{value}</span></div>",
                    unsafe_allow_html=True,
                )
    with col2:
        with st.container(border=True):
            open_t = [t for t in repo.tickets_for_tenant(user["id"])
                      if t["status"] not in ("Closed", "Resolved")]
            st.markdown(f"#### Open Maintenance ({len(open_t)})")
            if not open_t:
                st.caption("No open requests.")
            for t in open_t:
                st.markdown(
                    f"<div class='rh-row'><span class='rh-row-title'>{t['title']}</span>"
                    f"{ui.status_badge(t['status'])}</div>",
                    unsafe_allow_html=True,
                )

    # ---- Payment history chart ------------------------------------------- #
    periods = utils.recent_periods(6)
    totals = {p: 0.0 for p in periods}
    for p in repo.payments_for_lease(lease["id"]):
        per = p["period"] or (p["paid_at"][:7] if p["paid_at"] else None)
        if per in totals:
            totals[per] += float(p["amount"] or 0)
    if any(v > 0 for v in totals.values()):
        ui.section("Payments", "Last 6 months")
        chart_df = pd.DataFrame(
            {"Paid": [round(totals[p], 2) for p in periods]},
            index=[utils.period_label(p) for p in periods],
        )
        st.bar_chart(chart_df, color="#5E6B4D", height=200)

    ui.section("Recent Announcements")
    anns = repo.announcements_for_property(lease["property_id"], limit=5)
    if not anns:
        st.caption("Nothing new.")
    for a in anns:
        ui.announcement_card(a["body"], meta=a["created_at"][:16])


# --------------------------------------------------------------------------- #
# Payments — mock Stripe sandbox
# --------------------------------------------------------------------------- #

def _pay(user, lease) -> None:
    st.header("Pay Rent")
    if not lease:
        _no_lease()
        return

    # ownership re-check: this lease must belong to the logged-in tenant
    if not _owns_lease(user["id"], lease["id"]):
        st.error("You don't have access to this lease.")
        st.stop()

    balance = repo.lease_balance(lease["id"])
    st.metric("Current balance", utils.money_cents(max(balance, 0)))

    tab_pay, tab_history = st.tabs(["Make a payment", "Payment history & receipts"])

    with tab_pay:
        _checkout(user, lease, balance)

    with tab_history:
        _history(user, lease)


def _checkout(user, lease, balance) -> None:
    st.markdown(
        "<span class='rh-sandbox'>Sandbox checkout · Test mode — no real charge</span>",
        unsafe_allow_html=True,
    )
    st.caption("Use Stripe test card **4242 4242 4242 4242**, any future expiry, any CVC. "
               "Card **4000 0000 0000 0002** simulates a decline. Card numbers are never stored.")

    default_amount = float(max(balance, 0)) or float(lease["rent_amount"])
    with st.form("checkout", clear_on_submit=False):
        amount = st.number_input("Amount to pay (USD)", min_value=1.0,
                                 max_value=1_000_000.0, value=round(default_amount, 2),
                                 step=50.0,
                                 help="Pay your full balance or a partial amount.")
        st.text_input("Card number", key="cc_num", placeholder="4242 4242 4242 4242")
        c1, c2, c3 = st.columns(3)
        c1.text_input("Expiry (MM/YY)", key="cc_exp", placeholder="12/34")
        c2.text_input("CVC", key="cc_cvc", placeholder="123")
        c3.text_input("ZIP", key="cc_zip", placeholder="94123")
        submitted = st.form_submit_button(f"Pay {utils.money_cents(amount)}", type="primary")

    if submitted:
        card = payments.Card(
            number=st.session_state.get("cc_num", ""),
            exp=st.session_state.get("cc_exp", ""),
            cvc=st.session_state.get("cc_cvc", ""),
            zip=st.session_state.get("cc_zip", ""),
        )
        with st.spinner("Processing payment…"):
            import os
            import time
            time.sleep(float(os.environ.get("RENTAL_PAYMENT_DELAY", "1.0")))  # simulate round-trip
            result = payments.service.charge(lease["id"], float(amount), card)

        # Never persist the card; only the result's last4 is kept.
        if result.success:
            repo.record_payment(
                lease["id"], float(amount), "card_mock",
                tenant_id=user["id"], processor_ref=result.processor_ref,
                last4=result.last4, period=utils.current_period(),
                recorded_by=user["id"],
            )
            me = repo.get_user(user["id"])
            if me and me["email"]:
                notifications.payment_receipt(
                    me["email"], me["name"], utils.money_cents(amount),
                    f"{lease['property_name']} {lease['unit_label']}", "card")
            st.success(f"Payment of {utils.money_cents(amount)} succeeded!")
            with st.container(border=True):
                st.markdown("#### Receipt")
                rows = [
                    ("Amount", utils.money_cents(amount)),
                    ("Date", utils.today().strftime("%b %d, %Y")),
                    ("Card", f"•••• {result.last4}"),
                    ("Reference", result.processor_ref),
                ]
                for label, value in rows:
                    st.markdown(
                        f"<div class='rh-row'><span class='rh-row-sub'>{label}</span>"
                        f"<span class='rh-row-title'>{value}</span></div>",
                        unsafe_allow_html=True,
                    )
                st.caption("Simulated payment (test mode). Your balance and your "
                           "manager's rent roll have been updated.")
            st.button("Done", on_click=lambda: None)  # triggers a rerun to refresh balance
        else:
            st.error(result.error)


def _history(user, lease) -> None:
    pays = repo.payments_for_lease(lease["id"])
    if not pays:
        st.caption("No payments yet.")
        return
    for p in pays:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{utils.money_cents(p['amount'])}** · {p['paid_at'][:10]} · "
                     f"{p['method']}" + (f" •••• {p['last4']}" if p["last4"] else ""))
            c1.caption(f"Ref: {p['processor_ref'] or '—'} · period "
                       f"{utils.period_label(p['period']) if p['period'] else '—'} · "
                       f"status: {p['status']}")
            receipt = _receipt_text(user, lease, p)
            c2.download_button("Receipt", receipt,
                               file_name=f"receipt_{p['id']}.txt", mime="text/plain",
                               icon=":material/receipt_long:", key=f"rcpt_{p['id']}")

    # late fees explanation
    fees = [c for c in repo.attachments_for("lease", lease["id"])]  # noqa: F841
    late = _late_fee_charges(lease["id"])
    if late:
        st.subheader("Late Fees Applied")
        for f in late:
            st.write(f"• {utils.period_label(f['period'])}: {utils.money_cents(f['amount'])} "
                     f"— applied because rent was past the due date.")


def _receipt_text(user, lease, p) -> str:
    return (
        "RENTAL PAYMENT RECEIPT\n"
        "======================\n"
        f"Tenant:     {user['name']}\n"
        f"Property:   {lease['property_name']} — Unit {lease['unit_label']}\n"
        f"Amount:     {utils.money_cents(p['amount'])}\n"
        f"Date:       {p['paid_at']}\n"
        f"Method:     {p['method']}" + (f" (•••• {p['last4']})\n" if p['last4'] else "\n") +
        f"Reference:  {p['processor_ref'] or '—'}\n"
        f"Period:     {p['period'] or '—'}\n"
        f"Status:     {p['status']}\n"
        "\n(Test-mode / sandbox payment — no real charge was made.)\n"
    )


def _late_fee_charges(lease_id):
    import db
    return db.query_all(
        "SELECT * FROM charges WHERE lease_id=? AND type='late_fee' ORDER BY period",
        (lease_id,),
    )


# --------------------------------------------------------------------------- #
# Maintenance
# --------------------------------------------------------------------------- #

def _maintenance(user, lease) -> None:
    st.header("Maintenance Requests")
    if not lease:
        _no_lease()
        return

    with st.expander("Submit a new request", expanded=False, icon=":material/add:"):
        with st.form("renter_ticket", clear_on_submit=True):
            title = st.text_input("Title", placeholder="e.g. Leaky faucet in kitchen")
            desc = st.text_area("Description", placeholder="Describe the issue…")
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Category", CATEGORIES)
            prio = c2.selectbox("Priority", PRIORITIES, index=1)
            photo = st.file_uploader("Photo (optional)", type=["png", "jpg", "jpeg"])
            if st.form_submit_button("Submit request", type="primary"):
                if not title:
                    st.error("Please add a title.")
                else:
                    tid = repo.create_ticket(lease["unit_id"], user["id"], title,
                                             desc, cat, prio)
                    if photo is not None:
                        path, fname = storage.save_upload(photo, subdir="tickets")
                        repo.add_attachment("ticket", tid, path, fname, user["id"])
                    st.success("Request submitted! Your manager has been notified.")
                    st.rerun()

    st.divider()
    tickets = repo.tickets_for_tenant(user["id"])
    if not tickets:
        st.caption("You haven't submitted any requests.")
        return

    for t in tickets:
        with st.expander(f"{t['title']} — {t['status']}", icon=":material/build:"):
            st.markdown(
                ui.status_badge(t["status"]) + " " + ui.badge(t["priority"],
                    {"Emergency": "red", "High": "red", "Med": "amber", "Low": "gray"}
                    .get(t["priority"], "gray")),
                unsafe_allow_html=True,
            )
            st.write(t["description"] or "_No description._")
            st.caption(f"Category: {t['category']} · Priority: {t['priority']} · "
                       f"Submitted: {t['created_at'][:16]}")
            if t["assignee_name"]:
                st.caption(f"Assigned to: {t['assignee_name']}")
            for a in repo.attachments_for("ticket", t["id"]):
                try:
                    st.image(a["file_path"], width=240, caption=a["filename"])
                except Exception:
                    st.caption(f"Attachment · {a['filename']}")

            _status_timeline(t)

            ups = repo.ticket_updates(t["id"], tenant_visible_only=True)
            if ups:
                st.markdown("**Updates from your manager**")
                for u in ups:
                    st.write(f"• _{u['created_at'][:16]}_ — {u['body']}")

            with st.form(f"comment_{t['id']}", clear_on_submit=True):
                comment = st.text_input("Add a comment")
                if st.form_submit_button("Send"):
                    if comment.strip():
                        repo.add_ticket_update(t["id"], user["id"], comment.strip(),
                                               visible_to_tenant=True)
                        st.rerun()


def _status_timeline(t) -> None:
    flow = repo.STATUS_FLOW
    try:
        idx = flow.index(t["status"])
    except ValueError:
        idx = 0
    chips = []
    for i, s in enumerate(flow):
        cls = "done" if i < idx else ("now" if i == idx else "todo")
        chips.append(f"<span class='rh-step {cls}'>{s}</span>")
    st.markdown("<div class='rh-steps'>" + "".join(chips) + "</div>",
                unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Documents & profile
# --------------------------------------------------------------------------- #

def _documents(user, lease) -> None:
    st.header("Documents & Profile")
    st.subheader("Your Documents")
    if lease:
        docs = repo.attachments_for("lease", lease["id"])
        if not docs:
            st.caption("No lease documents have been shared yet.")
        for d in docs:
            try:
                with open(d["file_path"], "rb") as fh:
                    st.download_button(d["filename"], fh.read(),
                                       file_name=d["filename"], key=f"doc_{d['id']}",
                                       icon=":material/description:")
            except OSError:
                st.caption(f"{d['filename']} (unavailable)")

    st.divider()
    st.subheader("Profile")
    row = repo.get_user(user["id"])
    with st.form("profile"):
        name = st.text_input("Name", row["name"])
        email = st.text_input("Email", row["email"] or "")
        phone = st.text_input("Phone", row["phone"] or "")
        if st.form_submit_button("Save", type="primary"):
            import db
            db.execute("UPDATE users SET name=?, email=?, phone=? WHERE id=?",
                       (name, email, phone, user["id"]))
            st.session_state.user["name"] = name
            st.success("Profile updated.")
            st.rerun()
    st.caption("Proof of renters insurance upload — coming in Phase 2.")


def _announcements(user, lease) -> None:
    st.header("Announcements")
    if not lease:
        _no_lease()
        return
    anns = repo.announcements_for_property(lease["property_id"], limit=30)
    if not anns:
        st.caption("Nothing posted yet.")
    for a in anns:
        scope = a["property_name"] or "All tenants"
        ui.announcement_card(a["body"], scope=scope,
                             meta=f"{a['created_at'][:16]} · {a['author_name']}")


# --------------------------------------------------------------------------- #
# Ownership check
# --------------------------------------------------------------------------- #

def _owns_lease(user_id: int, lease_id: int) -> bool:
    import db
    row = db.query_one(
        "SELECT 1 FROM lease_tenants WHERE user_id=? AND lease_id=?",
        (user_id, lease_id),
    )
    return row is not None
