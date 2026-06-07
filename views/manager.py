"""Manager Portal — portfolio oversight, CRUD, rent, maintenance, reports."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

import auth
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


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

def _dashboard(user) -> None:
    st.header("Portfolio dashboard")
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
        ui.section("Rent status", utils.period_label(utils.current_period()))
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

        ui.section("Open maintenance tickets")
        oc = s["open_tickets"]
        prio_cards = "".join(
            f"<div class='rh-prio-card'><span class='dot {tone}'></span>"
            f"<div class='n'>{oc[label]}</div><div class='l'>{label}</div></div>"
            for label, tone in [("Emergency", "red"), ("High", "red"),
                                ("Med", "amber"), ("Low", "gray")]
        )
        st.markdown(f"<div class='rh-prio'>{prio_cards}</div>", unsafe_allow_html=True)

    with right:
        ui.section("Needs attention")
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

def _properties(user) -> None:
    st.header("Properties & units")
    show_archived = st.toggle("Show archived", value=False)
    props = repo.list_properties(include_archived=show_archived)

    if props:
        cols = st.columns(3)
        for i, p in enumerate(props):
            stt = repo.property_stats(p["id"])
            name = p["name"] + ("  (archived)" if p["status"] == "archived" else "")
            cols[i % 3].markdown(
                ui.property_card(
                    name, p["city"], p["address"], stt["units"], stt["occupied"],
                    stt["occupancy"], utils.money(stt["rent_roll"]),
                ),
                unsafe_allow_html=True,
            )

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
        return

    st.divider()
    st.subheader("Manage a property")
    pmap = {f"{p['name']} ({p['city']})": p for p in props}
    choice = st.selectbox("Select property", list(pmap.keys()))
    prop = pmap[choice]
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

def _tenants(user) -> None:
    st.header("Tenants & leases")
    leases = repo.active_leases()
    query = st.text_input("Search", placeholder="Filter by property, unit, or tenant…",
                          label_visibility="collapsed",
                          icon=":material/search:").strip().lower()
    rows = []
    for l in leases:
        tenants = ", ".join(t["name"] for t in repo.lease_tenants(l["id"])) or "—"
        haystack = f"{l['property_name']} {l['unit_label']} {tenants}".lower()
        if query and query not in haystack:
            continue
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

    st.divider()
    col_new, col_manage = st.columns(2)

    with col_new:
        st.subheader("New lease")
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
                        st.success("Lease created and unit marked occupied.")
                        st.rerun()

    with col_manage:
        st.subheader("Manage / end a lease")
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

            up = st.file_uploader("Upload lease document (PDF)", type=["pdf"],
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
    st.header("Rent & payments")
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
                st.success(f"Recorded {utils.money_cents(amount)} ({method}).")
                st.rerun()


# --------------------------------------------------------------------------- #
# Maintenance
# --------------------------------------------------------------------------- #

def _maintenance(user) -> None:
    st.header("Maintenance / work orders")
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
            repo.update_ticket(t["id"], status=status, priority=priority,
                               assignee_id=amap[assignee], cost=float(cost),
                               actor_id=user["id"])
            if note.strip():
                repo.add_ticket_update(t["id"], user["id"], note.strip(), visible)
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
        st.bar_chart(df)
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
