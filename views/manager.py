"""Manager Portal — portfolio oversight, CRUD, rent, maintenance, reports."""

from __future__ import annotations

import base64
import io

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import auth
import lease_pdf
import notifications
import repo
import storage
import ui
import utils

SECTIONS = [
    "Dashboard",
    "Properties & Units",
    "Tenants & Leases",
    "Rent & Payments",
    "Maintenance",
    "Reports",
    "Announcements",
    "Settings",
]

CATEGORIES = ["plumbing", "electrical", "HVAC", "appliance", "other"]
PRIORITIES = ["Low", "Med", "High", "Emergency"]
STATUS_BADGE = {
    "Paid": "Paid", "Partial": "Partial", "Overdue": "Overdue",
    "Upcoming": "Upcoming", "No charge": "No charge",
}


def render(user, section: str) -> None:
    auth.require_role(auth.MANAGER)  # server-side guard on every manager view
    if section == "Dashboard":
        _dashboard(user)
    elif section == "Properties & Units":
        _properties(user)
    elif section == "Tenants & Leases":
        _tenants(user)
    elif section == "Rent & Payments":
        _rent(user)
    elif section == "Maintenance":
        _maintenance(user)
    elif section == "Reports":
        _reports(user)
    elif section == "Announcements":
        _announcements(user)
    elif section == "Settings":
        _settings(user)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

def _dashboard(user) -> None:
    st.header("Portfolio Dashboard")
    st.caption(f"Current period: {utils.period_label(utils.current_period())}")
    s = repo.portfolio_summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rent expected", utils.money(s["expected"]))
    c2.metric("Collected", utils.money(s["collected"]),
              f"{s['collection_rate']*100:.0f}% of expected")
    c3.metric("Outstanding", utils.money(s["outstanding"]),
              f"{s['delinquent_count']} delinquent", delta_color="inverse")
    c4.metric("Occupancy", f"{s['occupancy']*100:.0f}%",
              f"{s['occupied_units']}/{s['total_units']} units")

    st.divider()
    left, right = st.columns([1, 1])

    with left:
        ui.section("Rent Status", utils.period_label(utils.current_period()))
        roll = repo.rent_roll()
        order = ["Paid", "Partial", "Overdue", "Upcoming"]
        counts = {k: 0 for k in order}
        for r in roll:
            if r["status"] in counts:
                counts[r["status"]] += 1
        badges = " ".join(
            ui.badge(f"{counts[k]} {k.lower()}",
                     {"Paid": "green", "Partial": "amber",
                      "Overdue": "red", "Upcoming": "gray"}[k])
            for k in order
        )
        st.markdown(badges, unsafe_allow_html=True)
        st.bar_chart(
            pd.DataFrame({"leases": [counts[k] for k in order]}, index=order),
            color="#5E6B4D", height=200,
        )

        ui.section("Open Maintenance Tickets")
        oc = s["open_tickets"]
        prio_cards = "".join(
            f"<div class='rh-prio-card'><span class='dot {tone}'></span>"
            f"<div class='n'>{oc[label]}</div><div class='l'>{label}</div></div>"
            for label, tone in [("Emergency", "red"), ("High", "red"),
                                ("Med", "amber"), ("Low", "gray")]
        )
        st.markdown(f"<div class='rh-prio'>{prio_cards}</div>", unsafe_allow_html=True)

    with right:
        ui.section("Needs Attention")
        items = repo.needs_attention()
        if not items:
            st.success("All clear — nothing needs attention right now.")
        tone = {"Overdue rent": "red", "Partial rent": "amber",
                "New ticket": "olive", "Lease expiring": "gray"}
        for it in items[:18]:
            st.markdown(
                f"<div class='rh-row'><span class='rh-row-sub'>{it['text']}</span>"
                f"{ui.badge(it['kind'], tone.get(it['kind'], 'gray'))}</div>",
                unsafe_allow_html=True,
            )


# --------------------------------------------------------------------------- #
# Properties & units
# --------------------------------------------------------------------------- #

def _open_property(pid) -> None:
    st.session_state["open_property"] = pid


def _properties(user) -> None:
    st.header("Properties & Units")

    # Clicking a property's button opens its detail view directly (in-session
    # rerun, so login is preserved — a full-page link would reset session state).
    sel_id = st.session_state.get("open_property")
    if sel_id is not None:
        _property_detail(sel_id, user)
        return

    show_archived = st.toggle("Show archived", value=False)
    props = repo.list_properties(include_archived=show_archived)

    if props:
        st.caption("Click a property to manage its units and details.")
        cols = st.columns(3)
        for i, p in enumerate(props):
            stt = repo.property_stats(p["id"])
            name = p["name"] + ("  (archived)" if p["status"] == "archived" else "")
            card = ui.property_card(
                name, p["city"], p["address"], stt["units"], stt["occupied"],
                stt["occupancy"], utils.money(stt["rent_roll"]),
            )
            with cols[i % 3]:
                # The whole card is clickable: the keyed container gets a stable
                # `st-key-pcard_<id>` class; CSS overlays a transparent button
                # across it. Stays in-session (no reload), so login is preserved.
                with st.container(key=f"pcard_{p['id']}"):
                    st.markdown(card, unsafe_allow_html=True)
                    st.button(f"Open {p['name']}  →", key=f"open_{p['id']}",
                              use_container_width=True,
                              on_click=_open_property, args=(p["id"],))

    with st.expander("Add a property", icon=":material/add:"):
        with st.form("add_property", clear_on_submit=True):
            name = st.text_input("Name")
            address = st.text_input("Street address")
            col1, col2 = st.columns(2)
            city = col1.text_input("City")
            state = col2.text_input("State", value="CA")
            ptype = st.selectbox("Type", ["Apartment", "Single-family", "Condo", "Duplex"])
            notes = st.text_area("Notes", "")
            if st.form_submit_button("Create property", type="primary"):
                if name and address and city:
                    repo.create_property(name, address, city, state, ptype, notes, user["id"])
                    st.success(f"Created {name}.")
                    st.rerun()
                else:
                    st.error("Name, address, and city are required.")

    if not props:
        ui.empty_state("building", "No properties yet",
                       "Add your first property above to start building your portfolio.")


def _close_property() -> None:
    st.session_state.pop("open_property", None)


def _property_detail(sel_id, user) -> None:
    """Full detail view for one property, reached by clicking its card."""
    prop = next((p for p in repo.list_properties(include_archived=True)
                 if str(p["id"]) == str(sel_id)), None)

    st.button("Back to properties", icon=":material/arrow_back:",
              on_click=_close_property)

    if not prop:
        st.warning("That property couldn't be found.")
        return

    st.subheader(prop["name"])
    st.caption(f"{prop['address']} · {prop['city']}, {prop['state']}")
    st.write("")
    _manage_property(prop, user)


def _manage_property(prop, user) -> None:
    tab_units, tab_edit, tab_danger = st.tabs(["Units", "Edit details", "Archive / delete"])

    with tab_units:
        units = repo.list_units(prop["id"])
        if units:
            udf = pd.DataFrame([{
                "Unit": u["label"], "Beds": u["bedrooms"], "Baths": u["bathrooms"],
                "Sq ft": u["square_feet"], "Market rent": utils.money(u["market_rent"]),
                "Status": u["status"],
            } for u in units])
            st.dataframe(udf, use_container_width=True, hide_index=True)

        with st.expander("Add a unit", icon=":material/add:"):
            with st.form("add_unit", clear_on_submit=True):
                label = st.text_input("Unit label (e.g. 3B)")
                c1, c2, c3 = st.columns(3)
                beds = c1.number_input("Bedrooms", 0, 10, 1)
                baths = c2.number_input("Bathrooms", 0.0, 10.0, 1.0, step=0.5)
                sqft = c3.number_input("Sq ft", 0, 10000, 700, step=50)
                rent = st.number_input("Market rent", 0, 100000, 3000, step=50)
                if st.form_submit_button("Add unit", type="primary"):
                    if label:
                        repo.create_unit(prop["id"], label, int(beds), float(baths),
                                         int(sqft), float(rent), user["id"])
                        st.success(f"Added unit {label}.")
                        st.rerun()
                    else:
                        st.error("Unit label is required.")

        # quick edit of a unit
        if units:
            with st.expander("Edit a unit", icon=":material/edit:"):
                umap = {u["label"]: u for u in units}
                ulabel = st.selectbox("Unit", list(umap.keys()), key="edit_unit_sel")
                u = umap[ulabel]
                with st.form("edit_unit"):
                    c1, c2, c3 = st.columns(3)
                    beds = c1.number_input("Bedrooms", 0, 10, int(u["bedrooms"]))
                    baths = c2.number_input("Bathrooms", 0.0, 10.0, float(u["bathrooms"]), step=0.5)
                    sqft = c3.number_input("Sq ft", 0, 10000, int(u["square_feet"] or 0), step=50)
                    rent = st.number_input("Market rent", 0, 100000,
                                           int(u["market_rent"]), step=50)
                    if st.form_submit_button("Save unit"):
                        repo.update_unit(u["id"], u["label"], int(beds), float(baths),
                                         int(sqft), float(rent), user["id"])
                        st.success("Unit updated.")
                        st.rerun()

    with tab_edit:
        with st.form("edit_property"):
            name = st.text_input("Name", prop["name"])
            address = st.text_input("Street address", prop["address"])
            c1, c2 = st.columns(2)
            city = c1.text_input("City", prop["city"])
            state = c2.text_input("State", prop["state"])
            types = ["Apartment", "Single-family", "Condo", "Duplex"]
            ptype = st.selectbox("Type", types,
                                 index=types.index(prop["type"]) if prop["type"] in types else 0)
            notes = st.text_area("Notes", prop["notes"] or "")
            if st.form_submit_button("Save changes", type="primary"):
                repo.update_property(prop["id"], name, address, city, state, ptype,
                                     notes, user["id"])
                st.success("Property updated.")
                st.rerun()

    with tab_danger:
        has_history = repo.property_has_history(prop["id"])
        if prop["status"] == "archived":
            st.info("This property is archived.")
            if st.button("Unarchive"):
                repo.unarchive_property(prop["id"], user["id"])
                st.rerun()
        else:
            st.write("**Archive** keeps all historical payment & maintenance records "
                     "(soft delete — preferred).")
            if st.button("Archive property", icon=":material/archive:"):
                repo.archive_property(prop["id"], user["id"])
                st.success("Archived.")
                st.rerun()

        st.divider()
        if has_history:
            st.warning("Hard delete is disabled — this property has leases, payments, "
                       "or maintenance history. Archive it instead.")
        else:
            st.write("No historical data exists, so this property can be permanently deleted.")
            if st.button("Hard delete (permanent)", icon=":material/delete:"):
                repo.hard_delete_property(prop["id"], user["id"])
                st.success("Deleted.")
                st.rerun()


# --------------------------------------------------------------------------- #
# Tenants & leases
# --------------------------------------------------------------------------- #

def _lease_pdf_for(lease_fields: dict, user) -> tuple[str, bytes]:
    """Build a lease PDF (bytes) + filename from a dict of lease fields."""
    data = lease_pdf.build_lease_pdf(
        landlord=user.get("name") or "RentHarbor Property Management",
        property_name=lease_fields["property_name"],
        property_address=lease_fields.get("property_address", ""),
        unit_label=lease_fields["unit_label"],
        tenants=lease_fields["tenants"],
        rent=lease_fields["rent"],
        deposit=lease_fields["deposit"],
        due_day=lease_fields["due_day"],
        late_fee=lease_fields["late_fee"],
        start_date=lease_fields["start_date"],
        end_date=lease_fields["end_date"],
    )
    safe = f"lease_{lease_fields['property_name']}_{lease_fields['unit_label']}.pdf"
    safe = safe.replace(" ", "_").replace("/", "-")
    return safe, data


def _lease_fields(lease, tenant_names) -> dict:
    """Map an active-lease row + tenant names to the lease_pdf field dict."""
    return {
        "property_name": lease["property_name"],
        "unit_label": lease["unit_label"],
        "tenants": tenant_names,
        "rent": lease["rent_amount"],
        "deposit": lease["deposit"],
        "due_day": lease["due_day"],
        "late_fee": lease["late_fee_amount"],
        "start_date": lease["start_date"],
        "end_date": lease["end_date"],
    }


def _show_lease_pdf(fname: str, data: bytes, heading: str) -> None:
    """Render a one-click download plus an inline preview (opens the PDF)."""
    ui.section(heading)
    st.download_button("Download lease PDF", data, file_name=fname,
                       mime="application/pdf", type="primary")
    b64 = base64.b64encode(data).decode()
    components.html(
        f"<iframe title='Lease preview' src='data:application/pdf;base64,{b64}' "
        f"style='width:100%;height:560px;border:1px solid #E7E7E0;border-radius:12px'></iframe>",
        height=580,
    )


def _tenants(user) -> None:
    st.header("Tenants & Leases")

    # Freshly created lease: show its generated PDF (preview + download) up top.
    pending = st.session_state.pop("new_lease_pdf", None)
    if pending:
        st.success("Lease created and unit marked occupied. Your lease document is ready.")
        _show_lease_pdf(pending[0], pending[1], "Lease Document")
        st.divider()

    leases = repo.active_leases()
    query = st.text_input("Search", placeholder="Filter by property, unit, or tenant…",
                          label_visibility="collapsed",
                          icon=":material/search:").strip().lower()
    rows = []
    filtered = []  # (lease, tenant_names) for the lease-documents list
    for l in leases:
        tnames = [t["name"] for t in repo.lease_tenants(l["id"])]
        tenants = ", ".join(tnames) or "—"
        haystack = f"{l['property_name']} {l['unit_label']} {tenants}".lower()
        if query and query not in haystack:
            continue
        filtered.append((l, tnames))
        rows.append({
            "Property": l["property_name"], "Unit": l["unit_label"], "Tenant(s)": tenants,
            "Rent": utils.money(l["rent_amount"]), "Due day": l["due_day"],
            "Start": l["start_date"], "End": l["end_date"],
            "Balance": utils.money(repo.lease_balance(l["id"])),
        })
    if rows:
        st.caption(f"{len(rows)} of {len(leases)} lease(s)"
                   + (f" matching “{query}”" if query else ""))
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    elif query:
        ui.empty_state("users", "No matches", f"No leases match “{query}”.")
    else:
        ui.empty_state("users", "No active leases yet",
                       "Create a lease below to assign a tenant to a vacant unit.")

    # Per-tenant lease document — download each existing lease's PDF directly.
    if filtered:
        with st.expander(f"Lease Documents ({len(filtered)})", icon=":material/description:"):
            for l, tnames in filtered:
                who = ", ".join(tnames) or "—"
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{l['property_name']} · {l['unit_label']}** — {who}")
                fname, data = _lease_pdf_for(_lease_fields(l, tnames), user)
                c2.download_button("Lease PDF", data, file_name=fname,
                                   mime="application/pdf", key=f"leasedoc_{l['id']}",
                                   use_container_width=True, icon=":material/download:")

    st.divider()
    col_new, col_manage = st.columns(2)

    with col_new:
        st.subheader("New Lease")
        vacants = repo.vacant_units()
        tenants_all = repo.list_tenants()
        if not vacants:
            st.info("No vacant units available.")
        else:
            vmap = {f"{u['property_name']} — {u['label']} "
                    f"({utils.money(u['market_rent'])})": u for u in vacants}
            tmap = {f"{t['name']} ({t['username']})": t for t in tenants_all}
            with st.form("new_lease", clear_on_submit=True):
                vsel = st.selectbox("Vacant unit", list(vmap.keys()))
                unit = vmap[vsel]
                tsel = st.multiselect("Tenant(s)", list(tmap.keys()),
                                      help="Select one or more (co-tenants supported).")
                c1, c2 = st.columns(2)
                rent = c1.number_input("Rent amount", 0, 100000,
                                       int(unit["market_rent"]), step=50)
                deposit = c2.number_input("Deposit", 0, 100000,
                                          int(unit["market_rent"]), step=50)
                c3, c4 = st.columns(2)
                due_day = c3.number_input("Due day", 1, 28, 1)
                late_fee = c4.number_input("Late fee", 0, 1000, 75, step=5)
                c5, c6 = st.columns(2)
                start = c5.date_input("Start date", utils.today())
                end = c6.date_input("End date", utils.add_months(utils.today(), 12))
                if st.form_submit_button("Create lease", type="primary"):
                    if not tsel:
                        st.error("Select at least one tenant.")
                    else:
                        tids = [tmap[t]["id"] for t in tsel]
                        repo.create_lease(unit["id"], tids, float(rent), float(deposit),
                                          int(due_day), float(late_fee),
                                          start.isoformat(), end.isoformat(), user["id"])
                        st.session_state["new_lease_pdf"] = _lease_pdf_for({
                            "property_name": unit["property_name"],
                            "unit_label": unit["label"],
                            "tenants": [tmap[t]["name"] for t in tsel],
                            "rent": rent, "deposit": deposit, "due_day": due_day,
                            "late_fee": late_fee,
                            "start_date": start.isoformat(), "end_date": end.isoformat(),
                        }, user)
                        st.rerun()

    with col_manage:
        st.subheader("Manage / End a Lease")
        if leases:
            lmap = {f"{l['property_name']} {l['unit_label']} — "
                    f"{', '.join(t['name'] for t in repo.lease_tenants(l['id'])) or '—'}": l
                    for l in leases}
            lsel = st.selectbox("Lease", list(lmap.keys()))
            lease = lmap[lsel]
            st.write(f"**Rent:** {utils.money(lease['rent_amount'])} · "
                     f"**Due day:** {lease['due_day']} · "
                     f"**Ends:** {lease['end_date']}")
            st.write(f"**Current balance:** {utils.money(repo.lease_balance(lease['id']))}")

            fname, data = _lease_pdf_for({
                "property_name": lease["property_name"],
                "unit_label": lease["unit_label"],
                "tenants": [t["name"] for t in repo.lease_tenants(lease["id"])],
                "rent": lease["rent_amount"], "deposit": lease["deposit"],
                "due_day": lease["due_day"], "late_fee": lease["late_fee_amount"],
                "start_date": lease["start_date"], "end_date": lease["end_date"],
            }, user)
            st.download_button("Generate lease PDF", data, file_name=fname,
                               mime="application/pdf", icon=":material/description:")

            up = st.file_uploader("Upload signed lease document (PDF)", type=["pdf"],
                                  key="lease_doc")
            if up is not None:
                path, fname = storage.save_upload(up, subdir="leases")
                repo.add_attachment("lease", lease["id"], path, fname, user["id"])
                st.success(f"Attached {fname}.")
            docs = repo.attachments_for("lease", lease["id"])
            for d in docs:
                st.caption(f"Attachment · {d['filename']}")

            st.divider()
            if st.button("Move-out / end lease (marks unit vacant)",
                         icon=":material/logout:"):
                repo.end_lease(lease["id"], user["id"])
                st.success("Lease ended; unit is now vacant.")
                st.rerun()


# --------------------------------------------------------------------------- #
# Rent & payments
# --------------------------------------------------------------------------- #

def _rent(user) -> None:
    st.header("Rent & Payments")
    tab_roll, tab_ledger, tab_behind, tab_record = st.tabs(
        ["Rent roll", "Payment ledger", "What's behind", "Record a payment"]
    )

    with tab_roll:
        roll = repo.rent_roll()
        df = pd.DataFrame([{
            "Property": r["property"], "Unit": r["unit"], "Tenant": r["tenant"],
            "Due": utils.money(r["charged"]), "Paid": utils.money(r["paid"]),
            "Balance": utils.money(r["balance"]),
            "Status": STATUS_BADGE.get(r["status"], r["status"]),
        } for r in roll])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(roll)} active leases · period "
                   f"{utils.period_label(utils.current_period())}")

    with tab_ledger:
        props = repo.list_properties()
        opt = ["All properties"] + [p["name"] for p in props]
        sel = st.selectbox("Filter by property", opt)
        pid = None if sel == "All properties" else next(p["id"] for p in props if p["name"] == sel)
        periods = ["All periods"] + utils.recent_periods(4)
        psel = st.selectbox("Filter by period", periods,
                            format_func=lambda x: x if x == "All periods" else utils.period_label(x))
        period = None if psel == "All periods" else psel
        ledger = repo.payment_ledger(property_id=pid, period=period)
        if ledger:
            df = pd.DataFrame([{
                "Date": p["paid_at"][:10], "Property": p["property_name"],
                "Unit": p["unit_label"], "Tenant": p["tenant_name"] or "—",
                "Method": p["method"], "Ref": p["processor_ref"] or "—",
                "Amount": utils.money_cents(p["amount"]),
            } for p in ledger])
            st.dataframe(df, use_container_width=True, hide_index=True)
            total = sum(p["amount"] for p in ledger)
            st.metric("Total in view", utils.money_cents(total))
        else:
            st.info("No payments match these filters.")

    with tab_behind:
        behind = repo.delinquencies()
        if not behind:
            st.success("No overdue or partial balances.")
        else:
            df = pd.DataFrame([{
                "Property": r["property"], "Unit": r["unit"], "Tenant": r["tenant"],
                "Balance": utils.money(r["balance"]), "Days late": r["days_late"],
                "Status": STATUS_BADGE.get(r["status"], r["status"]),
            } for r in behind])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.metric("Total outstanding", utils.money(sum(r["balance"] for r in behind)))

    with tab_record:
        st.caption("Record an offline payment (cash/check) and reconcile it.")
        leases = repo.active_leases()
        lmap = {f"{l['property_name']} {l['unit_label']} — "
                f"{', '.join(t['name'] for t in repo.lease_tenants(l['id'])) or '—'} "
                f"(bal {utils.money(repo.lease_balance(l['id']))})": l for l in leases}
        with st.form("record_payment", clear_on_submit=True):
            lsel = st.selectbox("Lease", list(lmap.keys()))
            lease = lmap[lsel]
            c1, c2 = st.columns(2)
            amount = c1.number_input("Amount", 0.0, 1_000_000.0,
                                     float(lease["rent_amount"]), step=50.0)
            method = c2.selectbox("Method", ["check", "cash"])
            period = st.selectbox("Apply to period", utils.recent_periods(4),
                                  index=3, format_func=utils.period_label)
            if st.form_submit_button("Record payment", type="primary"):
                tenants = repo.lease_tenants(lease["id"])
                tid = tenants[0]["id"] if tenants else None
                repo.record_payment(lease["id"], float(amount), method,
                                    tenant_id=tid, period=period, recorded_by=user["id"])
                if tenants and tenants[0]["email"]:
                    notifications.payment_receipt(
                        tenants[0]["email"], tenants[0]["name"],
                        utils.money_cents(amount),
                        f"{lease['property_name']} {lease['unit_label']}", method)
                st.success(f"Recorded {utils.money_cents(amount)} ({method}).")
                st.rerun()


# --------------------------------------------------------------------------- #
# Maintenance
# --------------------------------------------------------------------------- #

def _maintenance(user) -> None:
    st.header("Maintenance / Work Orders")
    props = repo.list_properties()
    c1, c2, c3 = st.columns(3)
    prop_opt = ["All"] + [p["name"] for p in props]
    fprop = c1.selectbox("Property", prop_opt)
    fstatus = c2.selectbox("Status", ["All"] + repo.STATUS_FLOW)
    fprio = c3.selectbox("Priority", ["All"] + PRIORITIES)

    pid = None if fprop == "All" else next(p["id"] for p in props if p["name"] == fprop)
    statuses = None if fstatus == "All" else [fstatus]
    prio = None if fprio == "All" else fprio
    tickets = repo.list_tickets(statuses=statuses, property_id=pid, priority=prio)

    st.caption(f"{len(tickets)} ticket(s)")
    for t in tickets:
        with st.expander(f"[{t['priority']}] {t['title']} — "
                         f"{t['property_name']} {t['unit_label']}  ·  {t['status']}",
                         icon=":material/build:"):
            _manager_ticket_detail(t, user)

    st.divider()
    with st.expander("Create a ticket on behalf of a tenant", icon=":material/add:"):
        _manager_create_ticket(user)


def _manager_ticket_detail(t, user) -> None:
    st.write(t["description"] or "_No description._")
    st.caption(f"Category: {t['category']} · Reported by: {t['reporter_name']} · "
               f"Created: {t['created_at'][:16]}")
    for a in repo.attachments_for("ticket", t["id"]):
        try:
            st.image(a["file_path"], width=240, caption=a["filename"])
        except Exception:
            st.caption(f"Attachment · {a['filename']}")

    with st.form(f"ticket_{t['id']}"):
        c1, c2, c3 = st.columns(3)
        status = c1.selectbox("Status", repo.STATUS_FLOW,
                              index=repo.STATUS_FLOW.index(t["status"])
                              if t["status"] in repo.STATUS_FLOW else 0)
        priority = c2.selectbox("Priority", PRIORITIES,
                                index=PRIORITIES.index(t["priority"])
                                if t["priority"] in PRIORITIES else 1)
        cost = c3.number_input("Cost", 0.0, 1_000_000.0, float(t["cost"]), step=10.0)
        managers = repo.list_managers()
        amap = {"— Unassigned —": None}
        amap.update({m["name"]: m["id"] for m in managers})
        cur_assignee = t["assignee_name"] or "— Unassigned —"
        akeys = list(amap.keys())
        assignee = st.selectbox("Assignee", akeys,
                                index=akeys.index(cur_assignee) if cur_assignee in akeys else 0)
        note = st.text_area("Add an update / note")
        visible = st.checkbox("Visible to tenant", value=True)
        if st.form_submit_button("Save", type="primary"):
            status_changed = status != t["status"]
            repo.update_ticket(t["id"], status=status, priority=priority,
                               assignee_id=amap[assignee], cost=float(cost),
                               actor_id=user["id"])
            if note.strip():
                repo.add_ticket_update(t["id"], user["id"], note.strip(), visible)
            if status_changed:
                rep = repo.get_user(t["reporter_id"])
                if rep and rep["email"]:
                    notifications.ticket_status_email(
                        rep["email"], rep["name"], t["title"], status,
                        f"{t['property_name']} {t['unit_label']}")
            st.success("Ticket updated.")
            st.rerun()

    ups = repo.ticket_updates(t["id"])
    if ups:
        st.markdown("**Activity**")
        for u in ups:
            tag = "" if u["visible_to_tenant"] else " _(internal)_"
            st.write(f"• _{u['created_at'][:16]}_ — **{u['author_name']}**{tag}: {u['body']}")


def _manager_create_ticket(user) -> None:
    props = repo.list_properties()
    pmap = {p["name"]: p for p in props}
    with st.form("mgr_create_ticket", clear_on_submit=True):
        psel = st.selectbox("Property", list(pmap.keys()))
        units = repo.list_units(pmap[psel]["id"])
        umap = {u["label"]: u for u in units}
        usel = st.selectbox("Unit", list(umap.keys()))
        title = st.text_input("Title")
        desc = st.text_area("Description")
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", CATEGORIES)
        prio = c2.selectbox("Priority", PRIORITIES, index=1)
        if st.form_submit_button("Create ticket", type="primary"):
            if title and umap:
                repo.create_ticket(umap[usel]["id"], user["id"], title, desc, cat, prio)
                st.success("Ticket created.")
                st.rerun()
            else:
                st.error("Title and a unit are required.")


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #

def _reports(user) -> None:
    st.header("Reports")
    tab1, tab2, tab3 = st.tabs(
        ["Rent collection", "Aging / outstanding", "Maintenance cost"]
    )

    with tab1:
        periods = utils.recent_periods(4)
        data = []
        for period in periods:
            roll = repo.rent_roll(period)
            data.append({
                "Period": utils.period_label(period),
                "Expected": sum(r["charged"] for r in roll),
                "Collected": sum(min(r["paid"], r["charged"]) for r in roll),
            })
        df = pd.DataFrame(data).set_index("Period")
        long = df.reset_index().melt("Period", var_name="Series", value_name="Amount")
        order = list(df.index)
        chart = (
            alt.Chart(long)
            .mark_bar()
            .encode(
                x=alt.X("Period:N", sort=order, title=None,
                        axis=alt.Axis(labelAngle=0)),
                xOffset=alt.XOffset("Series:N", sort=["Expected", "Collected"]),
                y=alt.Y("Amount:Q", title=None),
                color=alt.Color("Series:N", sort=["Expected", "Collected"],
                                scale=alt.Scale(domain=["Expected", "Collected"],
                                                range=["#7FB2E5", "#1565C0"]),
                                legend=alt.Legend(title=None, orient="bottom")),
                tooltip=["Period", "Series", alt.Tooltip("Amount:Q", format=",.0f")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.dataframe(df.map(utils.money), use_container_width=True)
        _csv_download(df.reset_index(), "rent_collection.csv")

    with tab2:
        roll = repo.rent_roll()
        buckets = {"0–30 days": 0.0, "31–60 days": 0.0, "60+ days": 0.0}
        for r in roll:
            if r["balance"] <= 0:
                continue
            d = r["days_late"]
            if d <= 30:
                buckets["0–30 days"] += r["balance"]
            elif d <= 60:
                buckets["31–60 days"] += r["balance"]
            else:
                buckets["60+ days"] += r["balance"]
        adf = pd.DataFrame({"Outstanding": buckets})
        st.bar_chart(adf)
        st.dataframe(adf.map(utils.money), use_container_width=True)
        _csv_download(adf.reset_index(), "aging_report.csv")

    with tab3:
        rows = repo.maintenance_cost_by_property()
        mdf = pd.DataFrame([{
            "Property": r["property_name"], "Tickets": r["tickets"],
            "Total cost": r["total_cost"],
        } for r in rows])
        if not mdf.empty:
            st.bar_chart(mdf.set_index("Property")["Total cost"])
            show = mdf.copy()
            show["Total cost"] = show["Total cost"].map(utils.money)
            st.dataframe(show, use_container_width=True, hide_index=True)
            _csv_download(mdf, "maintenance_cost.csv")


def _csv_download(df: pd.DataFrame, filename: str) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    st.download_button("Export CSV", buf.getvalue(), file_name=filename,
                       mime="text/csv", icon=":material/download:")


# --------------------------------------------------------------------------- #
# Announcements
# --------------------------------------------------------------------------- #

def _announcements(user) -> None:
    st.header("Announcements")
    props = repo.list_properties()
    with st.form("new_announcement", clear_on_submit=True):
        opts = ["All tenants (portfolio-wide)"] + [p["name"] for p in props]
        sel = st.selectbox("Audience", opts)
        body = st.text_area("Message", placeholder="e.g. Water shut off Tuesday 9am–12pm")
        if st.form_submit_button("Post announcement", type="primary"):
            if body.strip():
                pid = None if sel.startswith("All tenants") else \
                    next(p["id"] for p in props if p["name"] == sel)
                repo.create_announcement(pid, user["id"], body.strip())
                st.success("Posted.")
                st.rerun()
            else:
                st.error("Message can't be empty.")

    st.divider()
    ui.section("Recent")
    for a in repo.all_announcements():
        scope = a["property_name"] or "All tenants"
        ui.announcement_card(a["body"], scope=scope,
                             meta=f"{a['created_at'][:16]} · by {a['author_name']}")


# --------------------------------------------------------------------------- #
# Settings (owner / manager automation controls)
# --------------------------------------------------------------------------- #

def _send_rent_reminders() -> int:
    sent = 0
    period = utils.current_period()
    for r in repo.delinquencies():
        due = utils.due_date_for(period, r["due_day"])
        prop_unit = f"{r['property']} {r['unit']}"
        for t in repo.lease_tenants(r["lease_id"]):
            if t["email"] and notifications.rent_reminder(
                t["email"], t["name"], utils.money(r["balance"]),
                due.strftime("%b %d"), prop_unit):
                sent += 1
    return sent


def _settings(user) -> None:
    st.header("Settings")
    st.caption("Owner / manager controls. Each automation can be turned off here.")

    ui.section("Automated Late Fees")
    lf_on = repo.late_fees_enabled()
    new_lf = st.toggle(
        "Automatically charge a late fee when rent is overdue",
        value=lf_on,
        help="Applies each lease's late-fee amount once per period, after the "
             "grace window. Turn off anytime — existing fees are not removed.",
    )
    if new_lf != lf_on:
        repo.set_late_fees_enabled(new_lf)
        st.rerun()
    st.caption(f"Grace period: {repo.late_fee_grace_days()} days after the due date "
               "before a fee is applied.")
    if st.button("Run late-fee check now", icon=":material/bolt:"):
        n = repo.apply_late_fees(actor_id=user["id"])
        if n:
            st.success(f"Applied {n} late fee(s).")
        else:
            st.info("No late fees were due.")

    st.divider()
    ui.section("Email Notifications")
    if not notifications.is_configured():
        st.info("Email isn't set up yet. Add a `RESEND_API_KEY` in your Streamlit "
                "app secrets to enable payment receipts, maintenance updates, and "
                "rent reminders.")
    nt_on = notifications.enabled()
    new_nt = st.toggle(
        "Send automated emails (receipts, maintenance updates, reminders)",
        value=nt_on, disabled=not notifications.is_configured(),
    )
    if new_nt != nt_on:
        notifications.set_enabled(new_nt)
        st.rerun()
    if st.button("Send rent reminders now", icon=":material/mail:",
                 disabled=not notifications.can_send()):
        sent = _send_rent_reminders()
        st.success(f"Sent {sent} reminder(s).")
