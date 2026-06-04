"""Business-logic / repository layer.

Higher-level operations built on top of ``db``: balances, rent roll, atomic
payment recording, dashboard aggregates, maintenance workflow. View modules call
these instead of writing SQL, and ownership checks live here so a renter can
never read another tenant's records by manipulating IDs.
"""

from __future__ import annotations

import db
import utils


# --------------------------------------------------------------------------- #
# Users / tenants
# --------------------------------------------------------------------------- #

def get_user(user_id: int):
    return db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def list_managers():
    return db.query_all(
        "SELECT * FROM users WHERE role = 'MANAGER' ORDER BY name"
    )


def list_tenants():
    return db.query_all(
        "SELECT * FROM users WHERE role = 'RENTER' ORDER BY name"
    )


# --------------------------------------------------------------------------- #
# Properties & units
# --------------------------------------------------------------------------- #

def list_properties(include_archived: bool = False):
    sql = "SELECT * FROM properties"
    if not include_archived:
        sql += " WHERE status = 'active'"
    sql += " ORDER BY city, name"
    return db.query_all(sql)


def property_stats(property_id: int) -> dict:
    units = db.query_all("SELECT * FROM units WHERE property_id = ?", (property_id,))
    total = len(units)
    occupied = sum(1 for u in units if u["status"] == "occupied")
    rent_roll = sum(u["market_rent"] for u in units if u["status"] == "occupied")
    return {
        "units": total,
        "occupied": occupied,
        "vacant": total - occupied,
        "occupancy": (occupied / total) if total else 0.0,
        "rent_roll": rent_roll,
    }


def create_property(name, address, city, state, ptype, notes, actor_id) -> int:
    pid = db.execute(
        "INSERT INTO properties (name, address, city, state, type, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, address, city, state, ptype, notes),
    )
    db.audit(actor_id, "create", "property", pid, name)
    return pid


def update_property(property_id, name, address, city, state, ptype, notes, actor_id):
    db.execute(
        "UPDATE properties SET name=?, address=?, city=?, state=?, type=?, notes=? "
        "WHERE id=?",
        (name, address, city, state, ptype, notes, property_id),
    )
    db.audit(actor_id, "update", "property", property_id, name)


def property_has_history(property_id: int) -> bool:
    row = db.query_one(
        """
        SELECT COUNT(*) AS c
        FROM units u
        LEFT JOIN leases l ON l.unit_id = u.id
        LEFT JOIN payments p ON p.lease_id = l.id
        LEFT JOIN maintenance_tickets t ON t.unit_id = u.id
        WHERE u.property_id = ? AND (l.id IS NOT NULL OR p.id IS NOT NULL OR t.id IS NOT NULL)
        """,
        (property_id,),
    )
    return (row["c"] if row else 0) > 0


def archive_property(property_id, actor_id):
    db.execute("UPDATE properties SET status='archived' WHERE id=?", (property_id,))
    db.audit(actor_id, "archive", "property", property_id, "")


def unarchive_property(property_id, actor_id):
    db.execute("UPDATE properties SET status='active' WHERE id=?", (property_id,))
    db.audit(actor_id, "unarchive", "property", property_id, "")


def hard_delete_property(property_id, actor_id):
    """Only permitted when no historical data exists (caller must check)."""
    db.execute("DELETE FROM units WHERE property_id=?", (property_id,))
    db.execute("DELETE FROM properties WHERE id=?", (property_id,))
    db.audit(actor_id, "delete", "property", property_id, "hard delete")


def list_units(property_id: int):
    return db.query_all(
        "SELECT * FROM units WHERE property_id = ? ORDER BY label", (property_id,)
    )


def get_unit(unit_id: int):
    return db.query_one(
        """
        SELECT u.*, p.name AS property_name, p.city AS city
        FROM units u JOIN properties p ON p.id = u.property_id
        WHERE u.id = ?
        """,
        (unit_id,),
    )


def create_unit(property_id, label, bedrooms, bathrooms, sqft, market_rent, actor_id) -> int:
    uid = db.execute(
        "INSERT INTO units (property_id, label, bedrooms, bathrooms, square_feet, market_rent) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (property_id, label, bedrooms, bathrooms, sqft, market_rent),
    )
    db.audit(actor_id, "create", "unit", uid, label)
    return uid


def update_unit(unit_id, label, bedrooms, bathrooms, sqft, market_rent, actor_id):
    db.execute(
        "UPDATE units SET label=?, bedrooms=?, bathrooms=?, square_feet=?, market_rent=? "
        "WHERE id=?",
        (label, bedrooms, bathrooms, sqft, market_rent, unit_id),
    )
    db.audit(actor_id, "update", "unit", unit_id, label)


def vacant_units():
    return db.query_all(
        """
        SELECT u.*, p.name AS property_name
        FROM units u JOIN properties p ON p.id = u.property_id
        WHERE u.status = 'vacant' AND p.status = 'active'
        ORDER BY p.name, u.label
        """
    )


# --------------------------------------------------------------------------- #
# Leases & tenants
# --------------------------------------------------------------------------- #

def get_lease(lease_id: int):
    return db.query_one(
        """
        SELECT l.*, u.label AS unit_label, u.property_id,
               p.name AS property_name, p.city AS city
        FROM leases l
        JOIN units u ON u.id = l.unit_id
        JOIN properties p ON p.id = u.property_id
        WHERE l.id = ?
        """,
        (lease_id,),
    )


def lease_for_unit(unit_id: int):
    return db.query_one(
        "SELECT * FROM leases WHERE unit_id = ? AND status = 'active'", (unit_id,)
    )


def lease_tenants(lease_id: int):
    return db.query_all(
        """
        SELECT us.* FROM lease_tenants lt
        JOIN users us ON us.id = lt.user_id
        WHERE lt.lease_id = ?
        """,
        (lease_id,),
    )


def active_lease_for_tenant(tenant_id: int):
    return db.query_one(
        """
        SELECT l.*, u.label AS unit_label, u.property_id AS property_id,
               p.name AS property_name, p.city AS city
        FROM lease_tenants lt
        JOIN leases l ON l.id = lt.lease_id
        JOIN units u ON u.id = l.unit_id
        JOIN properties p ON p.id = u.property_id
        WHERE lt.user_id = ? AND l.status = 'active'
        ORDER BY l.start_date DESC LIMIT 1
        """,
        (tenant_id,),
    )


def create_lease(unit_id, tenant_ids, rent_amount, deposit, due_day, late_fee,
                 start_date, end_date, actor_id, generate_history=True) -> int:
    lease_id = db.execute(
        "INSERT INTO leases (unit_id, rent_amount, deposit, due_day, late_fee_amount, "
        "start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')",
        (unit_id, rent_amount, deposit, due_day, late_fee, start_date, end_date),
    )
    for tid in tenant_ids:
        db.execute(
            "INSERT INTO lease_tenants (lease_id, user_id) VALUES (?, ?)",
            (lease_id, tid),
        )
    db.execute("UPDATE units SET status='occupied' WHERE id=?", (unit_id,))
    if generate_history:
        ensure_current_charge(lease_id)
    db.audit(actor_id, "create", "lease", lease_id, f"unit {unit_id}")
    return lease_id


def end_lease(lease_id, actor_id):
    lease = get_lease(lease_id)
    db.execute("UPDATE leases SET status='ended' WHERE id=?", (lease_id,))
    if lease:
        db.execute("UPDATE units SET status='vacant' WHERE id=?", (lease["unit_id"],))
    db.audit(actor_id, "end", "lease", lease_id, "")


def ensure_current_charge(lease_id: int) -> None:
    """Make sure a rent charge exists for the current period."""
    lease = db.query_one("SELECT * FROM leases WHERE id=?", (lease_id,))
    if not lease:
        return
    period = utils.current_period()
    existing = db.query_one(
        "SELECT id FROM charges WHERE lease_id=? AND period=? AND type='rent'",
        (lease_id, period),
    )
    if not existing:
        due = utils.due_date_for(period, lease["due_day"]).isoformat()
        db.execute(
            "INSERT INTO charges (lease_id, type, amount, period, due_date) "
            "VALUES (?, 'rent', ?, ?, ?)",
            (lease_id, lease["rent_amount"], period, due),
        )


# --------------------------------------------------------------------------- #
# Balances & payments
# --------------------------------------------------------------------------- #

def lease_balance(lease_id: int) -> float:
    """balance = sum(charges) - sum(succeeded payments)."""
    charged = db.query_one(
        "SELECT COALESCE(SUM(amount),0) AS s FROM charges WHERE lease_id=?", (lease_id,)
    )["s"]
    paid = db.query_one(
        "SELECT COALESCE(SUM(amount),0) AS s FROM payments "
        "WHERE lease_id=? AND status='succeeded'",
        (lease_id,),
    )["s"]
    return round(charged - paid, 2)


def period_status(lease_id: int, period: str, due_day: int) -> dict:
    """Paid/Partial/Overdue/Upcoming for one lease in one period."""
    charged = db.query_one(
        "SELECT COALESCE(SUM(amount),0) AS s FROM charges WHERE lease_id=? AND period=?",
        (lease_id, period),
    )["s"]
    paid = db.query_one(
        "SELECT COALESCE(SUM(amount),0) AS s FROM payments "
        "WHERE lease_id=? AND period=? AND status='succeeded'",
        (lease_id, period),
    )["s"]
    balance = round(charged - paid, 2)
    due = utils.due_date_for(period, due_day)
    past_due = utils.today() > due

    if charged == 0:
        status = "No charge"
    elif balance <= 0:
        status = "Paid"
    elif paid > 0:
        status = "Partial"
    elif past_due:
        status = "Overdue"
    else:
        status = "Upcoming"
    return {"charged": charged, "paid": paid, "balance": balance,
            "status": status, "due_date": due, "days_late": max(0, (utils.today() - due).days)}


def record_payment(lease_id, amount, method, *, tenant_id=None, processor_ref=None,
                   last4=None, period=None, recorded_by=None, status="succeeded") -> int:
    """Atomically record a payment and mark the period's charge paid if cleared.

    A non-succeeded payment never marks rent as paid.
    """
    period = period or utils.current_period()
    with db._write_lock:  # noqa: SLF001 - single transactional write
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO payments (lease_id, tenant_id, amount, method, status, "
                "processor_ref, period, last4, recorded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lease_id, tenant_id, amount, method, status, processor_ref,
                 period, last4, recorded_by),
            )
            payment_id = cur.lastrowid
            if status == "succeeded":
                # mark the period's rent charge paid if fully covered
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) AS s FROM charges "
                    "WHERE lease_id=? AND period=?",
                    (lease_id, period),
                )
                charged = cur.fetchone()["s"]
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) AS s FROM payments "
                    "WHERE lease_id=? AND period=? AND status='succeeded'",
                    (lease_id, period),
                )
                paid = cur.fetchone()["s"]
                if charged > 0 and paid >= charged:
                    cur.execute(
                        "UPDATE charges SET status='paid' WHERE lease_id=? AND period=?",
                        (lease_id, period),
                    )
            conn.commit()
        finally:
            conn.close()
    db.audit(recorded_by or tenant_id, "payment", "lease", lease_id,
             f"{method} ${amount:.2f} ({status})")
    return payment_id


def payments_for_lease(lease_id: int):
    return db.query_all(
        "SELECT * FROM payments WHERE lease_id=? ORDER BY paid_at DESC", (lease_id,)
    )


def payment_ledger(property_id=None, period=None):
    sql = """
        SELECT p.*, l.unit_id, u.label AS unit_label, pr.name AS property_name,
               us.name AS tenant_name
        FROM payments p
        JOIN leases l ON l.id = p.lease_id
        JOIN units u ON u.id = l.unit_id
        JOIN properties pr ON pr.id = u.property_id
        LEFT JOIN users us ON us.id = p.tenant_id
        WHERE p.status = 'succeeded'
    """
    params: list = []
    if property_id:
        sql += " AND pr.id = ?"
        params.append(property_id)
    if period:
        sql += " AND p.period = ?"
        params.append(period)
    sql += " ORDER BY p.paid_at DESC"
    return db.query_all(sql, tuple(params))


def active_leases():
    return db.query_all(
        """
        SELECT l.*, u.label AS unit_label, u.property_id,
               pr.name AS property_name, pr.city AS city
        FROM leases l
        JOIN units u ON u.id = l.unit_id
        JOIN properties pr ON pr.id = u.property_id
        WHERE l.status = 'active' AND pr.status = 'active'
        ORDER BY pr.name, u.label
        """
    )


def rent_roll(period=None):
    period = period or utils.current_period()
    rows = []
    for lease in active_leases():
        st = period_status(lease["id"], period, lease["due_day"])
        tenants = ", ".join(t["name"] for t in lease_tenants(lease["id"])) or "—"
        rows.append({
            "lease_id": lease["id"],
            "property": lease["property_name"],
            "unit": lease["unit_label"],
            "tenant": tenants,
            "rent": lease["rent_amount"],
            "charged": st["charged"],
            "paid": st["paid"],
            "balance": st["balance"],
            "status": st["status"],
            "days_late": st["days_late"],
            "due_day": lease["due_day"],
        })
    return rows


def delinquencies(period=None):
    return [r for r in rent_roll(period) if r["status"] in ("Overdue", "Partial")]


# --------------------------------------------------------------------------- #
# Dashboard aggregates
# --------------------------------------------------------------------------- #

def portfolio_summary(period=None) -> dict:
    period = period or utils.current_period()
    roll = rent_roll(period)
    expected = sum(r["charged"] for r in roll)
    collected = sum(min(r["paid"], r["charged"]) for r in roll)
    outstanding = sum(max(r["balance"], 0) for r in roll)
    delinquent = [r for r in roll if r["status"] in ("Overdue", "Partial")]

    all_units = db.query_one(
        """
        SELECT COUNT(*) AS c FROM units u
        JOIN properties p ON p.id = u.property_id WHERE p.status='active'
        """
    )["c"]
    occ_units = db.query_one(
        """
        SELECT COUNT(*) AS c FROM units u
        JOIN properties p ON p.id = u.property_id
        WHERE p.status='active' AND u.status='occupied'
        """
    )["c"]

    return {
        "period": period,
        "expected": expected,
        "collected": collected,
        "outstanding": outstanding,
        "collection_rate": (collected / expected) if expected else 0.0,
        "delinquent_count": len(delinquent),
        "delinquents": delinquent,
        "total_units": all_units,
        "occupied_units": occ_units,
        "occupancy": (occ_units / all_units) if all_units else 0.0,
        "open_tickets": open_ticket_counts(),
    }


def needs_attention(period=None) -> list[dict]:
    period = period or utils.current_period()
    items: list[dict] = []
    for r in delinquencies(period):
        if r["status"] == "Overdue":
            items.append({"kind": "Overdue rent",
                          "text": f"{r['property']} {r['unit']} — {r['tenant']} "
                                  f"{utils.money(r['balance'])} ({r['days_late']}d late)"})
        else:
            items.append({"kind": "Partial rent",
                          "text": f"{r['property']} {r['unit']} — {r['tenant']} "
                                  f"{utils.money(r['balance'])} remaining"})
    for t in list_tickets(statuses=["New", "Acknowledged"]):
        items.append({"kind": "New ticket",
                      "text": f"[{t['priority']}] {t['title']} — {t['property_name']} {t['unit_label']}"})
    for lease in active_leases():
        end = lease["end_date"]
        try:
            from datetime import date
            ed = date.fromisoformat(end)
            days = (ed - utils.today()).days
            if 0 <= days <= 60:
                items.append({"kind": "Lease expiring",
                              "text": f"{lease['property_name']} {lease['unit_label']} "
                                      f"ends {end} ({days}d)"})
        except (ValueError, TypeError):
            pass
    return items


# --------------------------------------------------------------------------- #
# Maintenance
# --------------------------------------------------------------------------- #

PRIORITY_ORDER = {"Emergency": 0, "High": 1, "Med": 2, "Low": 3}
STATUS_FLOW = ["New", "Acknowledged", "In Progress", "On Hold", "Resolved", "Closed"]


def create_ticket(unit_id, reporter_id, title, description, category, priority) -> int:
    tid = db.execute(
        "INSERT INTO maintenance_tickets (unit_id, reporter_id, title, description, "
        "category, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (unit_id, reporter_id, title, description, category, priority),
    )
    db.audit(reporter_id, "create", "ticket", tid, title)
    return tid


def get_ticket(ticket_id: int):
    return db.query_one(
        """
        SELECT t.*, u.label AS unit_label, u.property_id,
               pr.name AS property_name,
               rep.name AS reporter_name, asg.name AS assignee_name
        FROM maintenance_tickets t
        JOIN units u ON u.id = t.unit_id
        JOIN properties pr ON pr.id = u.property_id
        LEFT JOIN users rep ON rep.id = t.reporter_id
        LEFT JOIN users asg ON asg.id = t.assignee_id
        WHERE t.id = ?
        """,
        (ticket_id,),
    )


def list_tickets(statuses=None, property_id=None, priority=None, unit_id=None):
    sql = """
        SELECT t.*, u.label AS unit_label, u.property_id,
               pr.name AS property_name,
               rep.name AS reporter_name, asg.name AS assignee_name
        FROM maintenance_tickets t
        JOIN units u ON u.id = t.unit_id
        JOIN properties pr ON pr.id = u.property_id
        LEFT JOIN users rep ON rep.id = t.reporter_id
        LEFT JOIN users asg ON asg.id = t.assignee_id
        WHERE 1=1
    """
    params: list = []
    if statuses:
        sql += " AND t.status IN (%s)" % ",".join("?" * len(statuses))
        params.extend(statuses)
    if property_id:
        sql += " AND pr.id = ?"
        params.append(property_id)
    if priority:
        sql += " AND t.priority = ?"
        params.append(priority)
    if unit_id:
        sql += " AND t.unit_id = ?"
        params.append(unit_id)
    rows = db.query_all(sql, tuple(params))
    return sorted(rows, key=lambda r: (PRIORITY_ORDER.get(r["priority"], 9), r["created_at"]))


def tickets_for_tenant(tenant_id: int):
    """Tickets on any unit the tenant currently leases."""
    return db.query_all(
        """
        SELECT t.*, u.label AS unit_label, pr.name AS property_name,
               asg.name AS assignee_name
        FROM maintenance_tickets t
        JOIN units u ON u.id = t.unit_id
        JOIN properties pr ON pr.id = u.property_id
        JOIN leases l ON l.unit_id = u.id
        JOIN lease_tenants lt ON lt.lease_id = l.id
        LEFT JOIN users asg ON asg.id = t.assignee_id
        WHERE lt.user_id = ?
        ORDER BY t.created_at DESC
        """,
        (tenant_id,),
    )


def open_ticket_counts() -> dict:
    rows = db.query_all(
        "SELECT priority, COUNT(*) AS c FROM maintenance_tickets "
        "WHERE status NOT IN ('Resolved','Closed') GROUP BY priority"
    )
    counts = {p: 0 for p in PRIORITY_ORDER}
    for r in rows:
        counts[r["priority"]] = r["c"]
    counts["total"] = sum(counts[p] for p in PRIORITY_ORDER)
    return counts


def update_ticket(ticket_id, *, status=None, priority=None, assignee_id=None,
                  cost=None, actor_id=None):
    fields, params = [], []
    if status is not None:
        fields.append("status=?"); params.append(status)
    if priority is not None:
        fields.append("priority=?"); params.append(priority)
    if assignee_id is not None:
        fields.append("assignee_id=?"); params.append(assignee_id)
    if cost is not None:
        fields.append("cost=?"); params.append(cost)
    if not fields:
        return
    fields.append("updated_at=datetime('now')")
    params.append(ticket_id)
    db.execute(f"UPDATE maintenance_tickets SET {', '.join(fields)} WHERE id=?", tuple(params))
    db.audit(actor_id, "update", "ticket", ticket_id,
             ", ".join(f"{f.split('=')[0]}" for f in fields if "=?" in f))


def add_ticket_update(ticket_id, author_id, body, visible_to_tenant=True) -> int:
    uid = db.execute(
        "INSERT INTO ticket_updates (ticket_id, author_id, body, visible_to_tenant) "
        "VALUES (?, ?, ?, ?)",
        (ticket_id, author_id, body, 1 if visible_to_tenant else 0),
    )
    db.execute("UPDATE maintenance_tickets SET updated_at=datetime('now') WHERE id=?",
               (ticket_id,))
    return uid


def ticket_updates(ticket_id, tenant_visible_only=False):
    sql = """
        SELECT tu.*, us.name AS author_name, us.role AS author_role
        FROM ticket_updates tu JOIN users us ON us.id = tu.author_id
        WHERE tu.ticket_id = ?
    """
    if tenant_visible_only:
        sql += " AND tu.visible_to_tenant = 1"
    sql += " ORDER BY tu.created_at ASC"
    return db.query_all(sql, (ticket_id,))


def maintenance_cost_by_property():
    return db.query_all(
        """
        SELECT pr.name AS property_name, COUNT(t.id) AS tickets,
               COALESCE(SUM(t.cost),0) AS total_cost
        FROM maintenance_tickets t
        JOIN units u ON u.id = t.unit_id
        JOIN properties pr ON pr.id = u.property_id
        GROUP BY pr.id ORDER BY total_cost DESC
        """
    )


# --------------------------------------------------------------------------- #
# Attachments & announcements
# --------------------------------------------------------------------------- #

def add_attachment(parent_type, parent_id, file_path, filename, uploaded_by) -> int:
    return db.execute(
        "INSERT INTO attachments (parent_type, parent_id, file_path, filename, uploaded_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (parent_type, parent_id, file_path, filename, uploaded_by),
    )


def attachments_for(parent_type, parent_id):
    return db.query_all(
        "SELECT * FROM attachments WHERE parent_type=? AND parent_id=? ORDER BY created_at",
        (parent_type, parent_id),
    )


def create_announcement(property_id, author_id, body) -> int:
    return db.execute(
        "INSERT INTO announcements (property_id, author_id, body) VALUES (?, ?, ?)",
        (property_id, author_id, body),
    )


def announcements_for_property(property_id, limit=10):
    return db.query_all(
        """
        SELECT a.*, us.name AS author_name, pr.name AS property_name
        FROM announcements a
        JOIN users us ON us.id = a.author_id
        LEFT JOIN properties pr ON pr.id = a.property_id
        WHERE a.property_id = ? OR a.property_id IS NULL
        ORDER BY a.created_at DESC LIMIT ?
        """,
        (property_id, limit),
    )


def all_announcements(limit=20):
    return db.query_all(
        """
        SELECT a.*, us.name AS author_name, pr.name AS property_name
        FROM announcements a
        JOIN users us ON us.id = a.author_id
        LEFT JOIN properties pr ON pr.id = a.property_id
        ORDER BY a.created_at DESC LIMIT ?
        """,
        (limit,),
    )
