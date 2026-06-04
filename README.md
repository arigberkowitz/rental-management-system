# 🏠 Rental Management System

A **Streamlit** web app that connects property managers with their tenants. One
codebase, one database, two role-gated experiences:

- **Manager Portal** — portfolio dashboard, property/unit & tenant/lease CRUD,
  rent roll, manual payment reconciliation, maintenance work orders, reports.
- **Renter Portal** — balance dashboard, **mock-Stripe rent payment**, maintenance
  requests with photo upload, documents, announcements.

This is the **v1 MVP** described in the PRD: seeded demo data, dummy logins, and a
simulated (mock) Stripe payment sandbox. No real Stripe keys or network calls.

## Quick start

```bash
cd rental-management-system
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/streamlit run app.py
```

Then open http://localhost:8501. The database (`rental.db`) is created and seeded
automatically on first run.

### Demo logins

| Username | Password | Role | Who |
|---|---|---|---|
| `ari` | `manager123` | Manager | Property manager (full portfolio) |
| `zach` | `owner123` | Manager | Owner (same access as manager in v1) |
| `rosa` | `tenant123` | Renter | Marina Heights #3B — **overdue** (demo the payment flow) |
| `marcus` | `tenant123` | Renter | Bridgeway Bayfront #5 — partial balance |
| `linh` | `tenant123` | Renter | Pacific View #2A — paid up |

(Plus ~30 more seeded tenants so the dashboard shows a realistic paid / partial /
overdue mix across 40 units in San Francisco and Sausalito.)

### Mock payment sandbox

On **Pay Rent**, use Stripe's well-known test cards:
- `4242 4242 4242 4242` → success (any future expiry, any CVC)
- `4000 0000 0000 0002` → simulated decline

Payments record a fake `pi_mock_…` reference and update balances instantly. Card
numbers are **never stored** — only the last 4 digits.

## Architecture

| File | Responsibility |
|---|---|
| `app.py` | Entry point: login, RBAC routing, sidebar nav |
| `auth.py` | bcrypt password hashing, authentication, `require_role` guard |
| `db.py` | SQLite schema + abstracted query helpers (swap-friendly data layer) |
| `repo.py` | Business logic: balances, rent roll, atomic payments, maintenance |
| `payments.py` | `PaymentService` interface + `MockPaymentService` (Stripe drops in later) |
| `seed.py` | Demo data generator (Sections 13–14 of the PRD) |
| `storage.py` | Local file storage for photos / lease PDFs |
| `views/manager.py` | Manager portal pages |
| `views/renter.py` | Renter portal pages |
| `test_smoke.py` | Headless render + payment-logic smoke tests |

**RBAC** is enforced server-side: every view calls `auth.require_role(...)` on the
data path, and renter queries are scoped to the logged-in tenant (a renter cannot
read another tenant's records by manipulating IDs).

## Run the tests

```bash
./.venv/bin/python test_smoke.py
```

Renders every portal section for both roles, exercises the mock payment success /
decline / privacy paths, and checks RBAC nav scoping.

## Deploying to Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. On https://share.streamlit.io, create an app pointing at `app.py`.
3. `requirements.txt` is picked up automatically.

> **Note:** Community Cloud has an ephemeral filesystem, so the SQLite DB and any
> uploaded files reset on restart — fine for a seeded demo. For durable data, swap
> `db.py` for a hosted Postgres (Neon/Supabase) via `st.connection`; the data layer
> is abstracted to make this straightforward. Put any future secrets (real Stripe
> keys) in Streamlit's secrets manager, never in the repo.

## What's v1 vs. later (per the PRD)

**v1 (this build):** two-portal RBAC, seeded data, property/unit/lease/tenant CRUD,
manager dashboard, rent roll + manual payment recording, maintenance tickets with
photos, renter dashboard, **mock** payments, basic reports (CSV export) and
announcements.

**Phase 2+:** live Stripe, real auth (invites / reset / autopay), automated late
fees, messaging, email/SMS notifications, durable Postgres, vendor portal, 2FA,
separate Owner vs. Manager roles.
