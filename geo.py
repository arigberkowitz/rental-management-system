"""Lightweight address -> coordinates for the portfolio map.

No network geocoding (keeps the app self-contained). Known seeded addresses get
exact-ish coordinates; anything else falls back to its city centroid with a
small deterministic offset so multiple pins in the same city don't stack.
"""

from __future__ import annotations

import hashlib

# Exact-ish coordinates for the seeded SF / Sausalito properties.
_ADDRESS = {
    "500 dolores st": (37.7596, -122.4269),
    "1450 bay st": (37.8063, -122.4286),
    "2200 lombard st": (37.7993, -122.4360),
    "100 bridgeway": (37.8591, -122.4783),
    "25 princess st": (37.8571, -122.4791),
}

# City centroids for the fallback.
_CITY = {
    "san francisco": (37.7749, -122.4194),
    "sausalito": (37.8591, -122.4853),
    "oakland": (37.8044, -122.2712),
    "berkeley": (37.8715, -122.2730),
    "san jose": (37.3382, -121.8863),
    "los angeles": (34.0522, -118.2437),
}

_DEFAULT = (37.7749, -122.4194)  # SF as a last resort


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _jitter(seed: str) -> tuple[float, float]:
    """Small deterministic lat/lon offset (~hundreds of meters) from a string."""
    h = hashlib.md5(seed.encode()).hexdigest()
    dx = (int(h[:4], 16) / 0xFFFF - 0.5) * 0.02
    dy = (int(h[4:8], 16) / 0xFFFF - 0.5) * 0.02
    return dx, dy


def coords(address: str, city: str) -> tuple[float, float]:
    a = _norm(address)
    if a in _ADDRESS:
        return _ADDRESS[a]
    base = _CITY.get(_norm(city), _DEFAULT)
    dx, dy = _jitter(f"{address}|{city}")
    return (round(base[0] + dx, 6), round(base[1] + dy, 6))
