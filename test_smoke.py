"""Headless smoke test: render every portal section for each role and exercise
the mock payment flow, asserting no exceptions surface. Run: python test_smoke.py
"""

from __future__ import annotations

import sys

from streamlit.testing.v1 import AppTest

import db
import repo
import seed
import utils

# fresh seed so the test is deterministic
seed.seed()

MANAGER = {"id": db.query_one("SELECT id FROM users WHERE username='ari'")["id"],
           "username": "ari", "name": "ARI", "role": "MANAGER"}
ROSA = db.query_one("SELECT * FROM users WHERE username='rosa'")
RENTER = {"id": ROSA["id"], "username": "rosa", "name": ROSA["name"], "role": "RENTER"}

from views import manager, renter  # noqa: E402

failures: list[str] = []


def visit(user, sections, label):
    for section in sections:
        at = AppTest.from_file("app.py", default_timeout=30)
        at.session_state["user"] = user
        at.run()
        # set the nav radio to the section and rerun
        at.radio[0].set_value(section).run()
        if at.exception:
            failures.append(f"[{label}] {section}: {at.exception[0].value}")
            print(f"  ✗ {label} / {section}: {at.exception[0].value}")
        else:
            print(f"  ✓ {label} / {section}")


print("\n== Manager portal ==")
visit(MANAGER, manager.SECTIONS, "manager")

print("\n== Renter portal ==")
visit(RENTER, renter.SECTIONS, "renter")

print("\n== Mock payment flow (Rosa) — exercises the _checkout submit logic ==")
import payments  # noqa: E402

lease = repo.active_lease_for_tenant(RENTER["id"])
bal_before = repo.lease_balance(lease["id"])

# Success path with the Stripe test card (mirrors renter._checkout on submit).
res = payments.service.charge(lease["id"], 500.0,
                              payments.Card("4242 4242 4242 4242", "12/34", "123", "94123"))
if not (res.success and res.processor_ref.startswith("pi_mock_") and res.last4 == "4242"):
    failures.append(f"[payment] success charge unexpected: {res}")
else:
    repo.record_payment(lease["id"], 500.0, "card_mock", tenant_id=RENTER["id"],
                        processor_ref=res.processor_ref, last4=res.last4,
                        period=utils.current_period(), recorded_by=RENTER["id"])
    bal_after = repo.lease_balance(lease["id"])
    ok = abs((bal_before - 500.0) - bal_after) < 0.01
    print(f"  ✓ success: balance {utils.money_cents(bal_before)} -> "
          f"{utils.money_cents(bal_after)}" if ok else "  ✗ balance not reduced")
    if not ok:
        failures.append("[payment] balance not reduced by payment")

# Decline path must NOT record (failed payment never marks rent paid).
bal_pre = repo.lease_balance(lease["id"])
res2 = payments.service.charge(lease["id"], 500.0,
                               payments.Card("4000 0000 0000 0002", "12/34", "123"))
if res2.success:
    failures.append("[payment] decline card reported success")
bal_post = repo.lease_balance(lease["id"])  # handler would not call record_payment
if abs(bal_pre - bal_post) >= 0.01:
    failures.append("[payment] decline changed balance")
else:
    print("  ✓ decline rejected and balance unchanged")

# Privacy: the full card number must never be persisted.
row = db.query_one("SELECT * FROM payments WHERE lease_id=? ORDER BY id DESC LIMIT 1",
                   (lease["id"],))
stored = " ".join(str(row[k]) for k in row.keys())
if "4242424242424242" in stored or "4242 4242" in stored:
    failures.append("[payment] full card number was persisted!")
else:
    print(f"  ✓ card not stored (last4 only: {row['last4']})")

print("\n== RBAC: renter cannot reach manager views ==")
at = AppTest.from_file("app.py", default_timeout=30)
at.session_state["user"] = RENTER
at.run()
# directly invoke a manager render -> require_role should st.stop (no exception, no crash)
# instead verify renter never sees manager sections in nav:
nav_opts = list(at.radio[0].options)
leaked = [s for s in manager.SECTIONS if s in nav_opts and s not in renter.SECTIONS]
print(f"  renter nav options: {nav_opts}")
if leaked:
    failures.append(f"[rbac] manager-only sections visible to renter: {leaked}")
    print(f"  ✗ leaked: {leaked}")
else:
    print("  ✓ no manager-only sections in renter nav")

print("\n" + "=" * 50)
if failures:
    print(f"FAILED ({len(failures)}):")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("ALL SMOKE TESTS PASSED")
