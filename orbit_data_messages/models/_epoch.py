"""CCSDS epoch string parsing and formatting utilities.

Provides a single canonical implementation for both date/time formats defined
in the spec: calendar (``YYYY-MM-DDThh:mm:ss[.d+][Z]``) and day-of-year
(``YYYY-DOYThh:mm:ss[.d+][Z]``).
"""
from __future__ import annotations

import re
from datetime import datetime
from datetime import timedelta


# 7.5.10: day-of-year format detected by a 3-digit day field at position 5.
_DOY_RE: re.Pattern[str] = re.compile(r"^\d{4}-(\d{3})T")

# Full CCSDS absolute date pattern (calendar and day-of-year forms).
_CCSDS_DATE_RE: re.Pattern[str] = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
    r"|\d{4}-\d{3}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
)

# Relative time tag: signed decimal number of seconds (CCSDS 6.2.2.3).
_RELATIVE_TIME_RE: re.Pattern[str] = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?")


def _validate_ccsds_date(v: str, field_name: str) -> str:
    """Validate a CCSDS absolute date string.

    Args:
        v (str): The date string to validate.
        field_name (str): Field name used in the error message.

    Returns:
        str: The validated date string, unchanged.

    Raises:
        ValueError: If ``v`` is not in calendar or day-of-year format.
    """
    if not _CCSDS_DATE_RE.fullmatch(v):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DDThh:mm:ss[.d+][Z] or "
            f"YYYY-DOYThh:mm:ss[.d+][Z]"
        )
    return v


def _validate_time_tag(v: str, field_name: str) -> str:
    """Accept either an absolute CCSDS date or a relative time in seconds.

    Args:
        v (str): The time-tag string to validate.
        field_name (str): Field name used in the error message.

    Returns:
        str: The validated time-tag string, unchanged.

    Raises:
        ValueError: If ``v`` is neither a valid CCSDS date nor a relative time.
    """
    if _CCSDS_DATE_RE.fullmatch(v) or _RELATIVE_TIME_RE.fullmatch(v):
        return v
    raise ValueError(
        f"{field_name} must be a CCSDS absolute date "
        f"(YYYY-MM-DDThh:mm:ss[Z] or YYYY-DOYThh:mm:ss[Z]) "
        f"or a relative time in seconds (e.g. 20157.26)."
    )


def _epoch_sort_key(epoch: str) -> str:
    """Return a lexicographically sortable calendar-format string for a CCSDS epoch.

    Converts day-of-year format to calendar format when necessary (§7.5.10).
    Both formats sort correctly by string comparison when used consistently;
    mixed sequences produce incorrect comparisons, so DOY epochs are
    normalized to calendar format before comparison.

    Args:
        epoch (str): A CCSDS epoch string in either calendar
            (``YYYY-MM-DDThh:mm:ss[.d][Z]``) or day-of-year
            (``YYYY-DOYThh:mm:ss[.d][Z]``) format.

    Returns:
        str: A normalized calendar-format epoch string suitable for
        lexicographic sorting.
    """
    e: str = epoch.rstrip("Z")
    if len(e) > 8 and e[4] == "-" and e[8] == "T" and e[5:8].isdigit():
        year: int = int(e[:4])
        doy: int = int(e[5:8])
        date: str = (datetime(year, 1, 1) + timedelta(days=doy - 1)).strftime("%Y-%m-%d")
        return date + "T" + e[9:]
    return e


def parse_ccsds_epoch(epoch: str) -> datetime:
    """Parses a CCSDS epoch string to a stdlib ``datetime``.

    Accepts both calendar (``YYYY-MM-DDThh:mm:ss``) and day-of-year
    (``YYYY-DOYThh:mm:ss``) formats, with optional sub-second precision and
    a trailing ``Z`` timezone designator.

    Args:
        epoch (str): A CCSDS epoch string.

    Returns:
        datetime: A timezone-naive ``datetime`` in UTC.
    """
    normalized: str = epoch.rstrip("Z")

    if _DOY_RE.match(normalized):
        # Day-of-year: YYYY-DOYThh:mm:ss[.d]
        date_part: str
        time_part: str
        date_part, time_part = normalized.split("T", 1)
        year: int = int(date_part[:4])
        doy: int = int(date_part[5:8])
        base_date: datetime = datetime(year, 1, 1) + timedelta(days=doy - 1)
        hour: str
        minute: str
        second: str
        hour, minute, second = time_part.split(":")
        second_float: float = float(second)
        microsecond: int = round((second_float % 1) * 1_000_000)
        return datetime(
            base_date.year, base_date.month, base_date.day,
            int(hour), int(minute), int(second_float), microsecond,
        )

    # Calendar: Python 3.11+ fromisoformat handles any sub-second precision.
    return datetime.fromisoformat(normalized)


def format_ccsds_epoch(dt: datetime) -> str:
    """Formats a stdlib ``datetime`` to a CCSDS calendar epoch string.

    Always produces the calendar format (``YYYY-MM-DDThh:mm:ss[.d+]``).
    Sub-second precision is included only when non-zero; trailing zeros are stripped.

    Args:
        dt (datetime): A timezone-naive ``datetime``.

    Returns:
        str: A CCSDS calendar epoch string, e.g. ``"2025-01-15T12:30:45.5"``.
    """
    result: str = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        result += f".{dt.microsecond:06d}".rstrip("0")
    return result
