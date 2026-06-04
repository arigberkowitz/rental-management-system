"""Small shared helpers: period math and formatting."""

from __future__ import annotations

from datetime import date, datetime


def today() -> date:
    return date.today()


def period_of(d: date) -> str:
    return d.strftime("%Y-%m")


def current_period() -> str:
    return period_of(today())


def add_months(d: date, delta: int) -> date:
    month_index = d.year * 12 + (d.month - 1) + delta
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def recent_periods(n: int, anchor: date | None = None) -> list[str]:
    """Return the last ``n`` periods ending with the anchor month (oldest first)."""
    anchor = anchor or today()
    return [period_of(add_months(anchor, -i)) for i in range(n - 1, -1, -1)]


def period_label(period: str) -> str:
    try:
        return datetime.strptime(period, "%Y-%m").strftime("%b %Y")
    except ValueError:
        return period


def due_date_for(period: str, due_day: int) -> date:
    year, month = (int(x) for x in period.split("-"))
    # clamp due_day to the month length
    day = min(due_day, 28)
    return date(year, month, day)


def money(value: float | None) -> str:
    return f"${(value or 0):,.0f}"


def money_cents(value: float | None) -> str:
    return f"${(value or 0):,.2f}"
