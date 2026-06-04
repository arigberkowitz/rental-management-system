"""Seed the database with demo data (Sections 13-14 of the PRD).

Idempotent-ish: running it drops and recreates the SQLite file so the demo
always starts from a known state. All passwords are dummy values, hashed with
bcrypt. Charges/payments are generated relative to *today* so the dashboard's
"current period" always lines up with the real calendar.
"""

from __future__ import annotations

import os
import random

import auth
import db
import repo
import utils

random.seed(42)  # deterministic demo data

# Named tenant -> (property name, unit label) per the PRD
NAMED_TENANTS = {
    "rosa":   ("Rosa Martinez", "Marina Heights Apartments", "3B"),
    "marcus": ("Marcus Lee", "Bridgeway Bayfront", "5"),
    "linh":   ("Linh Tran", "Pacific View Flats", "2A"),
}

# Force the current-period payment behavior for named demo tenants so each
# portal shows something interesting (Rosa owes -> can demo the payment flow).
NAMED_BEHAVIOR = {"rosa": "overdue", "marcus": "partial", "linh": "paid"}

EXTRA_TENANT_NAMES = [
    "Priya Shah", "David Okafor", "Emma Nilsson", "Jamal Wright", "Sofia Ricci",
    "Chen Wei", "Olivia Brooks", "Mateo Alvarez", "Hannah Cohen", "Noah Patel",
    "Grace Kim", "Liam Murphy", "Aisha Khan", "Ben Carter", "Maya Russo",
    "Tomas Vega", "Nina Fischer", "Omar Said", "Ella Novak", "Ryan Flores",
    "Yara Haddad", "Lucas Meyer", "Zoe Bennett", "Andre Costa", "Ivy Tran",
    "Carlos Mendez", "Freya Larsen", "Sam Adler", "Tara Singh", "Leo Castro",
    "Wendy Park", "Hugo Ferreira",
]

PROPERTIES = [
    # name, address, city, unit_count, label_scheme
    ("Marina Heights Apartments", "1450 Bay St", "San Francisco", 12, "AB"),
    ("Pacific View Flats", "2200 Lombard St", "San Francisco", 8, "AB"),
    ("Dolores Court", "500 Dolores St", "San Francisco", 4, "NUM"),
    ("Bridgeway Bayfront", "100 Bridgeway", "Sausalito", 10, "NUM"),
    ("Harbor View Cottages", "25 Princess St", "Sausalito", 6, "ALPHA"),
]

TICKET_SEEDS = [
    # (property, unit, title, category, priority, status, cost, note)
    ("Marina Heights Apartments", "3B", "Leaking kitchen faucet", "plumbing", "Med",
     "In Progress", 0, "Plumber scheduled for Thursday morning."),
    ("Bridgeway Bayfront", "5", "Dishwasher won't drain", "appliance", "Low",
     "Acknowledged", 0, "Will order a replacement pump."),
    ("Pacific View Flats", "2A", "No hot water", "plumbing", "High",
     "New", 0, ""),
    ("Marina Heights Apartments", "1A", "Heater not turning on", "HVAC", "High",
     "In Progress", 220, "Technician replaced thermostat; monitoring."),
    ("Dolores Court", "2", "Garbage disposal jammed", "appliance", "Low",
     "Resolved", 95, "Cleared jam, reset unit."),
    ("Bridgeway Bayfront", "2", "Burst pipe under sink — flooding", "plumbing",
     "Emergency", "In Progress", 0, "Water shut off; emergency plumber en route."),
    ("Harbor View Cottages", "C", "Front door lock sticking", "other", "Med",
     "Acknowledged", 0, ""),
    ("Marina Heights Apartments", "5A", "Bedroom outlet sparks", "electrical",
     "High", "New", 0, ""),
    ("Pacific View Flats", "4B", "AC dripping water", "HVAC", "Med",
     "On Hold", 0, "Waiting on tenant availability."),
    ("Bridgeway Bayfront", "8", "Smoke detector chirping", "electrical", "Low",
     "Closed", 15, "Replaced battery."),
]


def labels_for(scheme: str, count: int) -> list[str]:
    if scheme == "AB":
        out = []
        floor = 1
        while len(out) < count:
            out.extend([f"{floor}A", f"{floor}B"])
            floor += 1
        return out[:count]
    if scheme == "NUM":
        return [str(i) for i in range(1, count + 1)]
    if scheme == "ALPHA":
        return [chr(ord("A") + i) for i in range(count)]
    raise ValueError(scheme)


def rent_for(city: str, bedrooms: int) -> int:
    if city == "San Francisco":
        base = random.randint(3200, 5500)
    else:  # Sausalito
        base = random.randint(2800, 4800)
    base += (bedrooms - 1) * 350
    return int(round(base / 50) * 50)


def make_user(username, name, role, password, email=None, phone=None) -> int:
    return db.execute(
        "INSERT INTO users (username, name, email, phone, role, password_hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (username, name, email or f"{username}@example.com", phone, role,
         auth.hash_password(password)),
    )


def seed() -> None:
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_db()

    # --- Users ---------------------------------------------------------------
    ari_id = make_user("ari", "ARI", auth.MANAGER, "manager123", phone="415-555-0101")
    zach_id = make_user("zach", "Zach", auth.MANAGER, "owner123", phone="415-555-0102")

    tenant_ids: dict[str, int] = {}
    for username, (name, _prop, _unit) in NAMED_TENANTS.items():
        tenant_ids[username] = make_user(username, name, auth.RENTER, "tenant123")

    extra_ids: list[int] = []
    for i, name in enumerate(EXTRA_TENANT_NAMES):
        uname = "tenant%02d" % (i + 1)
        extra_ids.append(make_user(uname, name, auth.RENTER, "tenant123"))

    # --- Properties, units ---------------------------------------------------
    unit_index: dict[tuple[str, str], int] = {}  # (property, label) -> unit_id
    property_ids: dict[str, int] = {}
    for name, address, city, count, scheme in PROPERTIES:
        pid = repo.create_property(
            name, address, city, "CA", "Apartment",
            f"{count}-unit building in {city}.", ari_id,
        )
        property_ids[name] = pid
        for label in labels_for(scheme, count):
            bedrooms = random.choice([1, 1, 2, 2, 3])
            bathrooms = 1 if bedrooms == 1 else random.choice([1, 2])
            sqft = 550 + bedrooms * 250 + random.randint(-40, 120)
            rent = rent_for(city, bedrooms)
            uid = repo.create_unit(pid, label, bedrooms, bathrooms, sqft, rent, ari_id)
            unit_index[(name, label)] = uid

    # --- Decide occupancy ----------------------------------------------------
    all_units = list(unit_index.items())  # [((prop,label), uid), ...]
    random.shuffle(all_units)
    # Reserve the named-tenant units as occupied; leave ~6 vacant overall.
    named_unit_keys = {(prop, unit) for (_name, prop, unit) in NAMED_TENANTS.values()}
    # build occupied list
    vacant_target = 6
    occupied: list[tuple[tuple[str, str], int]] = []
    vacant_count = 0
    for key, uid in all_units:
        if key in named_unit_keys:
            occupied.append((key, uid))
        elif vacant_count < vacant_target:
            vacant_count += 1  # leave vacant
        else:
            occupied.append((key, uid))

    # --- Assign tenants to occupied units ------------------------------------
    available_tenants = list(extra_ids)
    random.shuffle(available_tenants)

    behaviors = _behavior_plan(len(occupied))
    today = utils.today()

    bi = 0
    for key, uid in occupied:
        prop_name, label = key
        # who lives here
        named_user = None
        forced_behavior = None
        for uname, (_nm, p, u) in NAMED_TENANTS.items():
            if (p, u) == key:
                named_user = tenant_ids[uname]
                forced_behavior = NAMED_BEHAVIOR.get(uname)
                break
        if named_user is not None:
            tids = [named_user]
        else:
            tids = [available_tenants.pop()] if available_tenants else []
        if not tids:
            continue

        unit = repo.get_unit(uid)
        rent = unit["market_rent"]
        due_day = random.choice([1, 1, 1, 5, 15])
        deposit = rent
        # lease dates: started 4-18 months ago; ends 1-10 months out (a few soon)
        start = utils.add_months(today, -random.randint(4, 18))
        end = utils.add_months(today, random.choice([1, 2, 8, 10, 12, 14]))
        lease_id = repo.create_lease(
            uid, tids, rent, deposit, due_day, 75,
            start.isoformat(), end.isoformat(), ari_id, generate_history=False,
        )
        behavior = forced_behavior or behaviors[bi]
        # Rosa is overdue -> make sure her due day has already passed.
        if forced_behavior == "overdue":
            due_day = 1
        _seed_charges_and_payments(lease_id, rent, due_day, tids[0],
                                   behavior, ari_id)
        bi += 1

    # --- Maintenance tickets -------------------------------------------------
    for prop, label, title, cat, prio, status, cost, note in TICKET_SEEDS:
        uid = unit_index.get((prop, label))
        if not uid:
            continue
        reporter = _tenant_of_unit(uid) or ari_id
        tid = repo.create_ticket(uid, reporter, title, "Reported by tenant. " + title,
                                 cat, prio)
        updates = {"status": status, "cost": cost} if cost else {"status": status}
        repo.update_ticket(tid, actor_id=ari_id, assignee_id=ari_id, **updates)
        if note:
            repo.add_ticket_update(tid, ari_id, note, visible_to_tenant=True)

    # --- Announcements -------------------------------------------------------
    repo.create_announcement(property_ids["Marina Heights Apartments"], ari_id,
                             "Water will be shut off Tuesday 9am-12pm for routine "
                             "maintenance. Please plan accordingly.")
    repo.create_announcement(property_ids["Bridgeway Bayfront"], ari_id,
                             "Parking lot will be resealed this weekend — please move "
                             "vehicles by Friday evening.")
    repo.create_announcement(None, zach_id,
                             "Reminder: rent is due on your lease's due day. Reach out "
                             "with any questions via the Messages tab.")

    print("Seed complete:")
    print(f"  users:      {db.query_one('SELECT COUNT(*) c FROM users')['c']}")
    print(f"  properties: {db.query_one('SELECT COUNT(*) c FROM properties')['c']}")
    print(f"  units:      {db.query_one('SELECT COUNT(*) c FROM units')['c']}")
    print(f"  leases:     {db.query_one('SELECT COUNT(*) c FROM leases')['c']}")
    print(f"  charges:    {db.query_one('SELECT COUNT(*) c FROM charges')['c']}")
    print(f"  payments:   {db.query_one('SELECT COUNT(*) c FROM payments')['c']}")
    print(f"  tickets:    {db.query_one('SELECT COUNT(*) c FROM maintenance_tickets')['c']}")


def _behavior_plan(n: int) -> list[str]:
    """Spread current-period payment behavior across occupied leases."""
    plan = (["paid"] * int(n * 0.60) + ["partial"] * int(n * 0.18) +
            ["overdue"] * int(n * 0.17))
    while len(plan) < n:
        plan.append("upcoming")
    random.shuffle(plan)
    return plan[:n]


def _seed_charges_and_payments(lease_id, rent, due_day, tenant_id, behavior, actor_id):
    """Create charges for the last 3 months + current, with payments to match."""
    periods = utils.recent_periods(4)  # oldest..current
    current = periods[-1]
    for period in periods:
        due = utils.due_date_for(period, due_day)
        db.execute(
            "INSERT INTO charges (lease_id, type, amount, period, due_date) "
            "VALUES (?, 'rent', ?, ?, ?)",
            (lease_id, rent, period, due.isoformat()),
        )

    # Past months always paid in full (online or offline).
    for period in periods[:-1]:
        method = random.choice(["card_mock", "card_mock", "check", "cash"])
        ref = "pi_mock_%s" % _hex(8) if method == "card_mock" else None
        last4 = "4242" if method == "card_mock" else None
        repo.record_payment(lease_id, rent, method, tenant_id=tenant_id,
                            processor_ref=ref, last4=last4, period=period,
                            recorded_by=(tenant_id if method == "card_mock" else actor_id))

    # Current month depends on behavior.
    if behavior == "paid":
        method = random.choice(["card_mock", "card_mock", "check"])
        ref = "pi_mock_%s" % _hex(8) if method == "card_mock" else None
        last4 = "4242" if method == "card_mock" else None
        repo.record_payment(lease_id, rent, method, tenant_id=tenant_id,
                            processor_ref=ref, last4=last4, period=current,
                            recorded_by=(tenant_id if method == "card_mock" else actor_id))
    elif behavior == "partial":
        part = round(rent * random.choice([0.4, 0.5, 0.6]), 2)
        repo.record_payment(lease_id, part, "card_mock", tenant_id=tenant_id,
                            processor_ref="pi_mock_%s" % _hex(8), last4="4242",
                            period=current, recorded_by=tenant_id)
    elif behavior == "overdue":
        # nothing paid; if well past due, apply a late fee charge (manager-applied)
        due = utils.due_date_for(current, due_day)
        if (utils.today() - due).days >= 5:
            db.execute(
                "INSERT INTO charges (lease_id, type, amount, period, due_date) "
                "VALUES (?, 'late_fee', 75, ?, ?)",
                (lease_id, current, due.isoformat()),
            )
    # 'upcoming': leave unpaid; due_day likely later in month


def _hex(n: int) -> str:
    import uuid
    return uuid.uuid4().hex[:n]


def _tenant_of_unit(unit_id: int):
    row = db.query_one(
        """
        SELECT lt.user_id FROM leases l
        JOIN lease_tenants lt ON lt.lease_id = l.id
        WHERE l.unit_id = ? AND l.status = 'active' LIMIT 1
        """,
        (unit_id,),
    )
    return row["user_id"] if row else None


if __name__ == "__main__":
    seed()
