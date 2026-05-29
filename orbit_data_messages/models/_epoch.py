"""CCSDS 502.0-B-3 §7.5.10 epoch string parsing and formatting utilities.

Provides a single canonical implementation for both date/time formats defined
in the spec: calendar (``YYYY-MM-DDThh:mm:ss[.d+][Z]``) and day-of-year
(``YYYY-DOYThh:mm:ss[.d+][Z]``).
"""
from __future__ import annotations

import re
from datetime import datetime
from datetime import timedelta


# §7.5.10 — day-of-year format detected by a 3-digit day field at position 5.
_DOY_RE = re.compile(r"^\d{4}-(\d{3})T")


def parse_ccsds_epoch(epoch: str) -> datetime:
    """Parses a CCSDS 502.0-B-3 §7.5.10 epoch string to a stdlib ``datetime``.

    Accepts both calendar (``YYYY-MM-DDThh:mm:ss``) and day-of-year
    (``YYYY-DOYThh:mm:ss``) formats, with optional sub-second precision and
    a trailing ``Z`` timezone designator.

    Args:
        epoch: A CCSDS §7.5.10 epoch string.

    Returns:
        A timezone-naive ``datetime`` in UTC.
    """
    normalized = epoch.rstrip("Z")

    if _DOY_RE.match(normalized):
        # Day-of-year: YYYY-DOYThh:mm:ss[.d]
        date_part, time_part = normalized.split("T", 1)
        year = int(date_part[:4])
        doy  = int(date_part[5:8])
        base_date = datetime(year, 1, 1) + timedelta(days=doy - 1)
        h, m, s = time_part.split(":")
        sec_f = float(s)
        usec  = round((sec_f % 1) * 1_000_000)
        return datetime(
            base_date.year, base_date.month, base_date.day,
            int(h), int(m), int(sec_f), usec,
        )

    # Calendar: Python 3.11+ fromisoformat handles any sub-second precision.
    return datetime.fromisoformat(normalized)


def format_ccsds_epoch(dt: datetime) -> str:
    """Formats a stdlib ``datetime`` to a CCSDS 502.0-B-3 §7.5.10 calendar epoch string.

    Always produces the calendar format (``YYYY-MM-DDThh:mm:ss[.d+]``).
    Sub-second precision is included only when non-zero; trailing zeros are stripped.

    Args:
        dt: A timezone-naive ``datetime``.

    Returns:
        A CCSDS §7.5.10 calendar epoch string, e.g. ``"2025-01-15T12:30:45.5"``.
    """
    result = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        result += f".{dt.microsecond:06d}".rstrip("0")
    return result
