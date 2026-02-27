"""Shared helper utilities for API routes."""

from datetime import date, datetime
from decimal import Decimal


def _rows(records) -> list[dict]:
    """Convert asyncpg Records to list of dicts with JSON-safe values."""
    result = []
    for row in records:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, (date, datetime)):
                d[k] = v.isoformat()
            elif isinstance(v, Decimal):
                d[k] = float(v)
        result.append(d)
    return result


class _ParamBuilder:
    """Track parameterized query values with auto-incrementing $N placeholders."""

    def __init__(self) -> None:
        self.conditions: list[str] = []
        self.params: list = []
        self._idx = 1

    def add(self, value: object) -> str:
        """Register a value and return its $N placeholder."""
        ph = f"${self._idx}"
        self.params.append(value)
        self._idx += 1
        return ph

    @property
    def where_sql(self) -> str:
        return " AND ".join(self.conditions)


def _parse_date_or_none(val: str | None) -> date | None:
    """Safely parse ISO date string, returning None on failure."""
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return None
