# SPDX-License-Identifier: Apache-2.0

"""
CCSDS epoch and time-system-aware wrapper.

Provides a single canonical implementation for both date/time formats defined
in the spec: calendar (``YYYY-MM-DDThh:mm:ss[.d+][Z]``) and day-of-year
(``YYYY-DOYThh:mm:ss[.d+][Z]``).

``TimeScaledEpoch``: A ``(datetime, time_system)`` pair returned by ``parse_ccsds_epoch``.
    Prevents silent arithmetic errors when epochs from different time systems (GPS, TAI, UTC)
    are compared. The wrapper raises on cross-scale comparisons.

``parse_ccsds_epoch``: Parses a CCSDS epoch string and returns a ``TimeScaledEpoch``.
    The ``datetime`` member uses ``tzinfo=UTC`` as a wire-encoding convention; its *numeric value*
    represents time in the specified ``time_system``.
"""

from __future__ import annotations

import re
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from pydantic.dataclasses import dataclass

from .values import TimeSystem

# Day-of-year format detected by a 3-digit day field at position 5.
_DOY_RE: re.Pattern[str] = re.compile(r"^\d{4}-(\d{3})T")

# CCSDS absolute date pattern (calendar and day-of-year forms).
_CCSDS_DATE_RE: re.Pattern[str] = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
    r"|\d{4}-\d{3}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
)

# Relative time tag: signed decimal number of seconds (6.2.2.3).
_REL_TIME_TAG_RE: re.Pattern[str] = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?")


@dataclass(frozen=True)
class TimeScaledEpoch:
    """
    A CCSDS epoch value paired with its explicit time system.

    The ``datetime`` attribute uses ``tzinfo=UTC`` as a wire-encoding convention
    only. The numeric value represents time in ``time_system``, which may differ
    from UTC by a fixed offset (e.g. GPS = UTC + 18 s, TAI = UTC + 37 s as of
    2017). Do not compare ``datetime`` values across different ``time_system``
    values; this class raises ``ValueError`` on such comparisons to prevent
    silent 18-second biases.

    Obtain instances via ``parse_ccsds_epoch(epoch, time_system)``.
    """

    datetime: datetime
    time_system: TimeSystem

    def __lt__(self, other: TimeScaledEpoch) -> bool:
        if self.time_system != other.time_system:
            raise ValueError(
                f"Cannot compare epochs across time systems: "
                f"{self.time_system!r} vs {other.time_system!r}. "
                "Convert both to a common time scale first."
            )
        return self.datetime < other.datetime

    def __le__(self, other: TimeScaledEpoch) -> bool:
        if self.time_system != other.time_system:
            raise ValueError(
                f"Cannot compare epochs across time systems: "
                f"{self.time_system!r} vs {other.time_system!r}."
            )
        return self.datetime <= other.datetime

    def __gt__(self, other: TimeScaledEpoch) -> bool:
        if self.time_system != other.time_system:
            raise ValueError(
                f"Cannot compare epochs across time systems: "
                f"{self.time_system!r} vs {other.time_system!r}."
            )
        return self.datetime > other.datetime

    def __ge__(self, other: TimeScaledEpoch) -> bool:
        if self.time_system != other.time_system:
            raise ValueError(
                f"Cannot compare epochs across time systems: "
                f"{self.time_system!r} vs {other.time_system!r}."
            )
        return self.datetime >= other.datetime


def validate_ccsds_date(v: str, field_name: str = "value") -> str:
    """
    Validate a CCSDS absolute date string: format and semantic range.

    Args:
        v (str): The date string to validate.
        field_name (str): Field name used in the error message.

    Returns:
        str: The validated date string, unchanged.

    Raises:
        ValueError: If ``v`` is not in calendar or day-of-year format, or if
            the date value is out of range (e.g. DOY 400 or month 13).
    """
    if not _CCSDS_DATE_RE.fullmatch(v):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DDThh:mm:ss[.d+][Z] or "
            f"YYYY-DOYThh:mm:ss[.d+][Z]"
        )
    # Semantic range check: reject "2025-400T00:00:00" (DOY out of range) and
    # "2025-13-40T00:00:00" (calendar month/day out of range) at construction time.
    try:
        _parse_ccsds_epoch(v)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} has an out-of-range date component: {exc}"
        ) from exc
    return v


def validate_time_tag(v: str, field_name: str = "value") -> str:
    """
    Accept either an absolute CCSDS date or a relative time in seconds.

    Check order:
    1. Absolute CCSDS date (calendar or day-of-year) - validated for semantic range.
    2. Relative time in seconds - signed decimal or scientific notation.

    Args:
        v (str): The time-tag string to validate.
        field_name (str): Field name used in the error message.

    Returns:
        str: The validated time-tag string, unchanged.

    Raises:
        ValueError: If ``v`` is neither a valid CCSDS date nor a relative time.
    """
    if _CCSDS_DATE_RE.fullmatch(v):
        # Also apply semantic range check for absolute dates used as time tags.
        validate_ccsds_date(v, field_name)
        return v
    if _REL_TIME_TAG_RE.fullmatch(v):
        return v
    raise ValueError(
        f"{field_name} must be a CCSDS absolute date "
        f"(YYYY-MM-DDThh:mm:ss[Z] or YYYY-DOYThh:mm:ss[Z]) "
        f"or a relative time in seconds (e.g. 20157.26)."
    )


def _normalize_epoch(epoch: str) -> str:
    """
    Return a canonical, lexicographically sortable string for a CCSDS absolute epoch.

    Parses the epoch (calendar or day-of-year, 7.5.10) and re-emits it in a single
    fixed-width calendar form with microsecond precision, so that:

    - day-of-year and calendar spellings of the same instant compare equal, and
    - fractional-second spellings of the same instant compare equal - e.g.
      ``...:00``, ``...:00.0`` and ``...:00.000`` all normalize identically.

    This makes ``<`` / ``==`` on the returned strings agree with chronological order
    and equality, which the OEM/OCM strictly-increasing and no-duplicate checks rely
    on: without canonical fractional seconds, ``...:00`` and ``...:00.0`` sort as
    distinct (the shorter string sorts first), so a functional duplicate would slip
    past a strictly-increasing check. Sub-microsecond precision is truncated (Python
    ``datetime`` limit, 7.5.10); two epochs differing only below 1 microsecond
    compare equal.

    Args:
        epoch (str): A CCSDS *absolute* epoch string in calendar
            (``YYYY-MM-DDThh:mm:ss[.d+][Z]``) or day-of-year
            (``YYYY-DOYThh:mm:ss[.d+][Z]``) format. Callers pass only
            already-validated absolute dates; relative time tags are compared on
            their own numeric path.

    Returns:
        str: A canonical ``YYYY-MM-DDThh:mm:ss.ffffff`` string.
    """
    return _parse_ccsds_epoch(epoch).strftime("%Y-%m-%dT%H:%M:%S.%f")


def _parse_ccsds_epoch(epoch: str) -> datetime:
    """
    Internal helper: parse a CCSDS epoch string to a UTC-aware ``datetime``.

    Raises ``ValueError`` if the date components are out of range (e.g. DOY 400).
    Used by ``_validate_ccsds_date`` for semantic checks and by ``parse_ccsds_epoch``.
    """
    normalized: str = epoch.rstrip("Z")

    if _DOY_RE.match(normalized):
        # Day-of-year: YYYY-DOYThh:mm:ss[.d]
        date_part: str
        time_part: str
        date_part, time_part = normalized.split("T", 1)
        year: int = int(date_part[:4])
        # timedelta arithmetic raises ValueError for doy > 365/366 implicitly
        # because the resulting datetime would be in the next year - detect it:
        if (doy := int(date_part[5:8])) < 1:
            raise ValueError(f"Day-of-year must be >= 1, got {doy}")
        base_date: datetime = datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=doy - 1)
        if base_date.year != year:
            raise ValueError(
                f"Day-of-year {doy} is out of range for year {year} "
                f"(max {366 if _is_leap_year(year) else 365})"
            )
        hour: str
        minute: str
        second: str
        hour, minute, second = time_part.split(":")
        second_float: float = float(second)
        microsecond: int = round((second_float % 1) * 1_000_000)
        return datetime(
            base_date.year,
            base_date.month,
            base_date.day,
            int(hour),
            int(minute),
            int(second_float),
            microsecond,
            tzinfo=UTC,
        )

    # Calendar: Python datetime is limited to microsecond precision (6 decimal
    # places). fromisoformat accepts spec-valid epochs with up to 16 fractional
    # digits (section 7.5.10) but silently truncates beyond microseconds.
    # fromisoformat raises ValueError for out-of-range month/day.
    return datetime.fromisoformat(normalized).replace(tzinfo=UTC)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def parse_ccsds_epoch(
    epoch: str,
    time_system: TimeSystem | None = None,
) -> TimeScaledEpoch:
    """
    Parse a CCSDS epoch string to a ``TimeScaledEpoch``.

    Accepts both calendar (``YYYY-MM-DDThh:mm:ss``) and day-of-year
    (``YYYY-DOYThh:mm:ss``) formats, with optional sub-second precision and
    a trailing ``Z`` timezone designator.

    The returned ``TimeScaledEpoch.datetime`` uses ``tzinfo=UTC`` as a
    wire-encoding convention. Its *numeric value* represents time in
    ``time_system``. For GPS (UTC+18 s) or TAI (UTC+37 s), the numeric value
    differs from UTC wall-clock time. Use ``TimeScaledEpoch`` comparisons rather
    than raw ``datetime`` arithmetic across messages with different time systems.

    Args:
        epoch (str): The CCSDS epoch string.
        time_system (TimeSystem | None): The time system the epoch is expressed
            in. Defaults to ``TimeSystem.UTC`` when ``None``.

    Returns:
        TimeScaledEpoch: Parsed epoch with its time-system tag.
    """
    ts: TimeSystem = time_system if time_system is not None else TimeSystem.UTC
    return TimeScaledEpoch(datetime=_parse_ccsds_epoch(epoch), time_system=ts)
