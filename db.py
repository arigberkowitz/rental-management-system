"""Data-access layer for the Rental Management System.

Supports two backends behind one tiny API so the rest of the app never has to
care which is in use:

* **Hosted Postgres** when a connection string is available
  (``st.secrets["DATABASE_URL"]`` or the ``DATABASE_URL`` env var) — used for the
  durable Streamlit Community Cloud deployment.
* **Local SQLite** otherwise — zero-config, so the app still runs locally with no
  secrets.

All SQL is written once using ``?`` placeholders, ``CURRENT_TIMESTAMP`` defaults
and a small set of dialect tokens; this module translates to the active backend.
Public helpers (``query_one``, ``query_all``, ``execute``, ``init_db``,
``is_seeded``, ``audit``) keep the same signatures, so callers are unchanged.
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import threading
from contextlib import contextmanager
from decimal import Decimal as _Decimal

DB_PATH = os.environ.get(
    "RENTAL_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "rental.db"),
)


def _resolve_database_url() -> str | None:
    """Read the Postgres URL from the env or Streamlit secrets, else None."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:  # st.secrets access can raise when no secrets file exists -> ignore
        import streamlit as st

        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    return None


DATABASE_URL = _resolve_database_url()
IS_POSTGRES = bool(DATABASE_URL)

# Imported lazily so SQLite-only installs don't need the Postgres driver.
if IS_POSTGRES:  # pragma: no cover - exercised only with a Postgres backend
    import psycopg2
    import psycopg2.extras

# Writes are serialized; required for SQLite, harmless for Postgres.
_write_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Connections, placeholders, row normalization
# --------------------------------------------------------------------------- #

def _connect():
    if IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Backwards-compatible alias (kept in case other modules import it).
get_connection = _connect


def _cursor(conn):
    if IS_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def _translate(sql: str) -> str:
    """SQLite uses ``?`` placeholders; Postgres (psycopg2) uses ``%s``."""
    return sql.replace("?", "%s") if IS_POSTGRES else sql


def _run(cur, sql: str, params):
    """Execute with backend-appropriate placeholders / empty-params handling."""
    if IS_POSTGRES:
        cur.execute(_translate(sql), tuple(params) if params else None)
    else:
        cur.execute(sql, tuple(params))


def _norm(value):
    """Make Postgres values behave like SQLite's (timestamps as strings, etc.)."""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return str(value)
    if isinstance(value, _Decimal):
        return float(value)
    return value


def _row(row):
    if row is None:
        return None
    if IS_POSTGRES:
        return {k: _norm(v) for k, v in row.items()}
    return row  # sqlite3.Row already supports ["key"] / .keys()


def _rows(rows):
    return [_row(r) for r in rows]


# --------------------------------------------------------------------------- #
# Public query helpers (unchanged signatures)
# --------------------------------------------------------------------------- #

def query_all(sql: str, params: tuple = ()):
    conn = _connect()
    try:
        cur = _cursor(conn)
        _run(cur, sql, params)
        return _rows(cur.fetchall())
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()):
    conn = _connect()
    try:
        cur = _cursor(conn)
        _run(cur, sql, params)
        return _row(cur.fetchone())
    finally:
        conn.close()


def _new_id(cur, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get("id")
    return row[0]


def execute(sql: str, params: tuple = ()) -> int | None:
    """Run a write statement; returns the new row id for INSERTs.

    On Postgres there is no ``cursor.lastrowid``, so INSERTs are given a
    ``RETURNING id`` clause (every table has an ``id`` column).
    """
    with _write_lock:
        conn = _connect()
        try:
            cur = _cursor(conn)
            if IS_POSTGRES:
                stmt = _translate(sql)
                is_insert = stmt.lstrip()[:6].lower() == "insert"
                if is_insert and "returning" not in stmt.lower():
                    stmt = stmt.rstrip().rstrip(";") + " RETURNING id"
                cur.execute(stmt, tuple(params) if params else None)
                rid = _new_id(cur, cur.fetchone()) if is_insert else None
                conn.commit()
                return rid
            cur.execute(sql, tuple(params))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def executemany(sql: str, seq_of_params) -> None:
    with _write_lock:
        conn = _connect()
        try:
            cur = _cursor(conn)
            cur.executemany(_translate(sql) if IS_POSTGRES else sql, list(seq_of_params))
            conn.commit()
        finally:
            conn.close()


class _Tx:
    """Cursor wrapper used inside :func:`transaction` for atomic multi-step writes."""

    def __init__(self, conn):
        self.conn = conn
        self.cur = _cursor(conn)

    def one(self, sql: str, params: tuple = ()):
        _run(self.cur, sql, params)
        return _row(self.cur.fetchone())

    def run(self, sql: str, params: tuple = ()):
        _run(self.cur, sql, params)

    def insert(self, sql: str, params: tuple = ()) -> int | None:
        if IS_POSTGRES:
            stmt = _translate(sql)
            if "returning" not in stmt.lower():
                stmt = stmt.rstrip().rstrip(";") + " RETURNING id"
            self.cur.execute(stmt, tuple(params) if params else None)
            return _new_id(self.cur, self.cur.fetchone())
        self.cur.execute(sql, tuple(params))
        return self.cur.lastrowid


@contextmanager
def transaction():
    """Atomic write transaction across both backends (commit/rollback)."""
    with _write_lock:
        conn = _connect()
        try:
            yield _Tx(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Schema (dialect-aware)
# --------------------------------------------------------------------------- #
#   {PK}   -> autoincrementing integer primary key
#   {REAL} -> floating-point money/measure column
#   {TS}   -> timestamp column (stored as TEXT in SQLite, TIMESTAMP in Postgres)

SCHEMA_TEMPLATE = """
CREATE TABLE IF NOT EXISTS users (
    id            {PK},
    username      TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    email         TEXT,
    phone         TEXT,
    role          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS properties (
    id         {PK},
    name       TEXT NOT NULL,
    address    TEXT NOT NULL,
    city       TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'CA',
    type       TEXT NOT NULL DEFAULT 'Apartment',
    notes      TEXT,
    status     TEXT NOT NULL DEFAULT 'active',
    created_at {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS units (
    id          {PK},
    property_id INTEGER NOT NULL REFERENCES properties(id),
    label       TEXT NOT NULL,
    bedrooms    INTEGER NOT NULL DEFAULT 1,
    bathrooms   {REAL} NOT NULL DEFAULT 1,
    square_feet INTEGER,
    market_rent {REAL} NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'vacant'
);

CREATE TABLE IF NOT EXISTS leases (
    id              {PK},
    unit_id         INTEGER NOT NULL REFERENCES units(id),
    rent_amount     {REAL} NOT NULL,
    deposit         {REAL} NOT NULL DEFAULT 0,
    due_day         INTEGER NOT NULL DEFAULT 1,
    late_fee_amount {REAL} NOT NULL DEFAULT 75,
    late_fee_policy TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS lease_tenants (
    id       {PK},
    lease_id INTEGER NOT NULL REFERENCES leases(id),
    user_id  INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS charges (
    id         {PK},
    lease_id   INTEGER NOT NULL REFERENCES leases(id),
    type       TEXT NOT NULL DEFAULT 'rent',
    amount     {REAL} NOT NULL,
    period     TEXT NOT NULL,
    due_date   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id           {PK},
    lease_id     INTEGER NOT NULL REFERENCES leases(id),
    tenant_id    INTEGER REFERENCES users(id),
    amount       {REAL} NOT NULL,
    method       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'succeeded',
    processor_ref TEXT,
    period       TEXT,
    last4        TEXT,
    paid_at      {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by  INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS maintenance_tickets (
    id          {PK},
    unit_id     INTEGER NOT NULL REFERENCES units(id),
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    assignee_id INTEGER REFERENCES users(id),
    title       TEXT NOT NULL,
    description TEXT,
    category    TEXT NOT NULL DEFAULT 'other',
    priority    TEXT NOT NULL DEFAULT 'Med',
    status      TEXT NOT NULL DEFAULT 'New',
    cost        {REAL} NOT NULL DEFAULT 0,
    created_at  {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_updates (
    id               {PK},
    ticket_id        INTEGER NOT NULL REFERENCES maintenance_tickets(id),
    author_id        INTEGER NOT NULL REFERENCES users(id),
    body             TEXT NOT NULL,
    visible_to_tenant INTEGER NOT NULL DEFAULT 1,
    created_at       {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attachments (
    id          {PK},
    parent_type TEXT NOT NULL,
    parent_id   INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    filename    TEXT,
    uploaded_by INTEGER REFERENCES users(id),
    created_at  {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS announcements (
    id          {PK},
    property_id INTEGER REFERENCES properties(id),
    author_id   INTEGER NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    created_at  {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        {PK},
    actor_id  INTEGER,
    action    TEXT NOT NULL,
    entity    TEXT,
    entity_id INTEGER,
    detail    TEXT,
    timestamp {TS} NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_prefs (
    id    {PK},
    key   TEXT UNIQUE NOT NULL,
    value TEXT
);
"""

# Drop order respects foreign keys (children first).
_TABLES = [
    "audit_log", "announcements", "attachments", "ticket_updates",
    "maintenance_tickets", "payments", "charges", "lease_tenants",
    "leases", "units", "properties", "users", "app_prefs",
]


def _schema() -> str:
    if IS_POSTGRES:
        return SCHEMA_TEMPLATE.format(
            PK="SERIAL PRIMARY KEY", REAL="DOUBLE PRECISION", TS="TIMESTAMP")
    return SCHEMA_TEMPLATE.format(
        PK="INTEGER PRIMARY KEY AUTOINCREMENT", REAL="REAL", TS="TEXT")


def init_db() -> None:
    schema = _schema()
    with _write_lock:
        conn = _connect()
        try:
            if IS_POSTGRES:
                cur = conn.cursor()
                for stmt in (s.strip() for s in schema.split(";")):
                    if stmt:
                        cur.execute(stmt)
            else:
                conn.executescript(schema)  # SQLite-only multi-statement helper
            conn.commit()
        finally:
            conn.close()


def reset() -> None:
    """Drop everything and recreate empty tables (used by the seeder)."""
    if IS_POSTGRES:
        with _write_lock:
            conn = _connect()
            try:
                cur = conn.cursor()
                for t in _TABLES:
                    cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
                conn.commit()
            finally:
                conn.close()
    elif os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()


def is_seeded() -> bool:
    try:
        row = query_one("SELECT COUNT(*) AS c FROM users")
        return bool(row) and row["c"] > 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Small key/value prefs + audit log
# --------------------------------------------------------------------------- #

def get_pref(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_prefs WHERE key=?", (key,))
    return row["value"] if row else default


def set_pref(key: str, value: str) -> None:
    """Upsert a small key/value preference (ON CONFLICT works in both backends)."""
    execute(
        "INSERT INTO app_prefs (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, str(value)),
    )


def audit(actor_id, action: str, entity: str, entity_id, detail: str = "") -> None:
    execute(
        "INSERT INTO audit_log (actor_id, action, entity, entity_id, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, entity, entity_id, detail),
    )
