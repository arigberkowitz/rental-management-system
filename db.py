"""Data-access layer for the Rental Management System.

Uses the stdlib ``sqlite3`` driver. All SQL lives behind the helpers in this
module so the storage engine can be swapped (e.g. for hosted Postgres) without
touching view code -- as called for in the PRD's "keep the data layer
abstracted" note.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "RENTAL_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "rental.db"),
)

# sqlite connections are not shareable across threads; Streamlit reruns can hop
# threads, so we open a fresh connection per call and keep things simple.
_write_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_cursor(commit: bool = False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """Run a write statement; returns lastrowid."""
    with _write_lock:
        with get_cursor(commit=True) as cur:
            cur.execute(sql, params)
            return cur.lastrowid


def executemany(sql: str, seq_of_params) -> None:
    with _write_lock:
        with get_cursor(commit=True) as cur:
            cur.executemany(sql, seq_of_params)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    email         TEXT,
    phone         TEXT,
    role          TEXT NOT NULL,                 -- MANAGER | RENTER (future: OWNER/VENDOR/ADMIN)
    password_hash TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS properties (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    address    TEXT NOT NULL,
    city       TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'CA',
    type       TEXT NOT NULL DEFAULT 'Apartment',
    notes      TEXT,
    status     TEXT NOT NULL DEFAULT 'active',   -- active | archived
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS units (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    label       TEXT NOT NULL,
    bedrooms    INTEGER NOT NULL DEFAULT 1,
    bathrooms   REAL NOT NULL DEFAULT 1,
    square_feet INTEGER,
    market_rent REAL NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'vacant'   -- occupied | vacant
);

CREATE TABLE IF NOT EXISTS leases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id         INTEGER NOT NULL REFERENCES units(id),
    rent_amount     REAL NOT NULL,
    deposit         REAL NOT NULL DEFAULT 0,
    due_day         INTEGER NOT NULL DEFAULT 1,
    late_fee_amount REAL NOT NULL DEFAULT 75,
    late_fee_policy TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active' -- active | ended
);

CREATE TABLE IF NOT EXISTS lease_tenants (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id INTEGER NOT NULL REFERENCES leases(id),
    user_id  INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS charges (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id   INTEGER NOT NULL REFERENCES leases(id),
    type       TEXT NOT NULL DEFAULT 'rent',     -- rent | late_fee
    amount     REAL NOT NULL,
    period     TEXT NOT NULL,                     -- YYYY-MM
    due_date   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',      -- open | paid
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id     INTEGER NOT NULL REFERENCES leases(id),
    tenant_id    INTEGER REFERENCES users(id),
    amount       REAL NOT NULL,
    method       TEXT NOT NULL,                   -- card_mock | cash | check
    status       TEXT NOT NULL DEFAULT 'succeeded',
    processor_ref TEXT,
    period       TEXT,
    last4        TEXT,
    paid_at      TEXT NOT NULL DEFAULT (datetime('now')),
    recorded_by  INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS maintenance_tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id     INTEGER NOT NULL REFERENCES units(id),
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    assignee_id INTEGER REFERENCES users(id),
    title       TEXT NOT NULL,
    description TEXT,
    category    TEXT NOT NULL DEFAULT 'other',
    priority    TEXT NOT NULL DEFAULT 'Med',      -- Low | Med | High | Emergency
    status      TEXT NOT NULL DEFAULT 'New',      -- New|Acknowledged|In Progress|On Hold|Resolved|Closed
    cost        REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ticket_updates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id        INTEGER NOT NULL REFERENCES maintenance_tickets(id),
    author_id        INTEGER NOT NULL REFERENCES users(id),
    body             TEXT NOT NULL,
    visible_to_tenant INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_type TEXT NOT NULL,                    -- ticket | lease
    parent_id   INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    filename    TEXT,
    uploaded_by INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS announcements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER REFERENCES properties(id),
    author_id   INTEGER NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id  INTEGER,
    action    TEXT NOT NULL,
    entity    TEXT,
    entity_id INTEGER,
    detail    TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_prefs (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_pref(key: str, default: str | None = None) -> str | None:
    """Read a small key/value preference (e.g. an autopay flag)."""
    row = query_one("SELECT value FROM app_prefs WHERE key=?", (key,))
    return row["value"] if row else default


def set_pref(key: str, value: str) -> None:
    """Upsert a small key/value preference."""
    execute(
        "INSERT INTO app_prefs (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def init_db() -> None:
    with _write_lock:
        conn = get_connection()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


def is_seeded() -> bool:
    row = query_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    if not row:
        return False
    return (query_one("SELECT COUNT(*) AS c FROM users") or {"c": 0})["c"] > 0


def audit(actor_id, action: str, entity: str, entity_id, detail: str = "") -> None:
    execute(
        "INSERT INTO audit_log (actor_id, action, entity, entity_id, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, entity, entity_id, detail),
    )
