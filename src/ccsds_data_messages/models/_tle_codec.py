# SPDX-License-Identifier: Apache-2.0

"""
Fixed-column encoding for NORAD Two-Line Element sets.

Pure formatting helpers that turn a mapped set of TLE field values (``_TleFields``)
into the two 69-character element lines; the mod-10 checksum, decimal-point-assumed
fields, Alpha-5 satellite numbers, and column layout. The domain mapping from an OMM
lives in ``models/conversions.py`` (``omm_to_tle``); the ``TLE`` value object itself
is in ``models/tle.py``. Column layout follows the de-facto NORAD/space-track.org
definition (https://www.space-track.org/documentation#tle).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._epoch import parse_ccsds_epoch
from .values import TimeSystem

# Alpha-5 letters: A-Z excluding I and O (which resemble 1 and 0). Index 0 maps to
# the leading value 10, so the encodable range is 100000 (A0000) to 339999 (Z9999).
_ALPHA5_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_LEGACY_NORAD_ID_MAX = 99_999
_ALPHA5_NORAD_ID_MAX = 339_999

# International designator: YYYY-NNNP{PP} (UN OOSA index), e.g. "1995-025A".
_INTL_DESIGNATOR_RE = re.compile(r"^(\d{4})-(\d{3})([A-Za-z]{1,3})$")


@dataclass(frozen=True)
class _TleFields:
    """
    TLE field values mapped from an OMM, ready for column encoding.

    Decouples the domain mapping (which OMM field feeds which TLE field) from the
    column formatting done by ``_encode_lines``.
    """

    norad_cat_id: int
    classification: str
    international_designator: str
    epoch: str
    time_system: TimeSystem | str
    n_dot: float
    n_ddot: float
    bstar: float
    ephemeris_type: int
    element_set_no: int
    inclination: float
    ra_of_asc_node: float
    eccentricity: float
    arg_of_pericenter: float
    mean_anomaly: float
    mean_motion: float
    rev_at_epoch: int


def _encode_lines(fields: _TleFields) -> tuple[str, str]:
    """Encode ``fields`` into the two 69-character TLE lines (checksums included)."""
    return _encode_line1(fields), _encode_line2(fields)


def _encode_line1(f: _TleFields) -> str:
    """Assemble TLE line 1 (columns 1-68) and append its checksum."""
    body = (
        f"1 {_alpha5(f.norad_cat_id)}{f.classification} "
        f"{_intl_designator(f.international_designator)} "
        f"{_epoch_yyddd(f.epoch, f.time_system)} "
        f"{_signed_decimal_fraction(f.n_dot)} "
        f"{_assumed_decimal_exp(f.n_ddot)} {_assumed_decimal_exp(f.bstar)} "
        f"{f.ephemeris_type:1d} {f.element_set_no:4d}"
    )
    return f"{body}{_checksum(body)}"


def _encode_line2(f: _TleFields) -> str:
    """Assemble TLE line 2 (columns 1-68) and append its checksum."""
    # Eccentricity is a 7-digit decimal-point-assumed field (0.0005013 -> "0005013").
    eccentricity = f"{round(f.eccentricity * 1e7):07d}"
    body = (
        f"2 {_alpha5(f.norad_cat_id)} {f.inclination:8.4f} "
        f"{f.ra_of_asc_node % 360.0:8.4f} {eccentricity} "
        f"{f.arg_of_pericenter % 360.0:8.4f} {f.mean_anomaly % 360.0:8.4f} "
        f"{f.mean_motion:11.8f}{f.rev_at_epoch:5d}"
    )
    return f"{body}{_checksum(body)}"


def _alpha5(norad_cat_id: int) -> str:
    """
    Encode a satellite catalog number as a 5-character Alpha-5 field.

    Numbers up to 99999 are zero-padded; 100000-339999 use a leading letter
    (A-Z excluding I and O) followed by the last four digits.

    Raises:
        ValueError: If ``norad_cat_id`` is negative or exceeds 339999.
    """
    if norad_cat_id < 0:
        raise ValueError(f"NORAD_CAT_ID must be non-negative, got {norad_cat_id}.")
    if norad_cat_id <= _LEGACY_NORAD_ID_MAX:
        return f"{norad_cat_id:05d}"
    if norad_cat_id <= _ALPHA5_NORAD_ID_MAX:
        leading, remainder = divmod(norad_cat_id, 10_000)
        return f"{_ALPHA5_LETTERS[leading - 10]}{remainder:04d}"
    raise ValueError(
        f"NORAD_CAT_ID {norad_cat_id} exceeds the Alpha-5 maximum of {_ALPHA5_NORAD_ID_MAX}; "
        "it cannot be represented in the 5-character TLE satellite-number field."
    )


def _intl_designator(object_id: str) -> str:
    """
    Convert a UN OOSA designator (``YYYY-NNNP{PP}``) to the 8-character TLE field.

    Produces last-two-year + launch-number + piece (left-justified in three
    columns). Non-standard identifiers (e.g. ``UNKNOWN``) yield eight spaces.
    """
    if (match := _INTL_DESIGNATOR_RE.match(object_id)) is None:
        return " " * 8
    year, launch, piece = match.groups()
    return f"{year[2:]}{launch}{piece.upper():<3}"


def _epoch_yyddd(epoch: str, time_system: TimeSystem | str) -> str:
    """
    Format a CCSDS epoch as the TLE ``YYDDD.DDDDDDDD`` field (14 characters).

    Two-digit year plus day-of-year with an 8-digit fractional day. Parsing reuses
    ``parse_ccsds_epoch`` so calendar and day-of-year spellings both work. The time
    system only tags the parsed instant (the numeric epoch is identical either way),
    so a non-enum string is tolerated.
    """
    scale = time_system if isinstance(time_system, TimeSystem) else None
    moment = parse_ccsds_epoch(epoch, scale).datetime
    year_start = moment.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    day_value = (moment - year_start).total_seconds() / 86_400 + 1
    return f"{moment.year % 100:02d}{day_value:012.8f}"


def _signed_decimal_fraction(value: float) -> str:
    """
    Format a fractional value as the 10-character ``[sign].NNNNNNNN`` TLE field.

    Used for the first derivative of mean motion (columns 34-43), which shows an
    explicit decimal point. The value must be strictly less than 1 in magnitude.

    Raises:
        ValueError: If ``abs(value) >= 1`` (does not fit the fixed field).
    """
    if abs(value) >= 1:
        raise ValueError(
            f"Value {value} does not fit the '.NNNNNNNN' TLE field (must be < 1)."
        )
    sign = "-" if value < 0 else " "
    return f"{sign}.{f'{abs(value):.8f}'[2:]}"  # ".NNNNNNNN" from "0.NNNNNNNN"


def _assumed_decimal_exp(value: float) -> str:
    """
    Format a value as the 8-character decimal-point-assumed exponential TLE field.

    Layout ``[sign]NNNNN[esign]E`` encodes ``±0.NNNNN x 10**=/-E`` (columns 45-52 for
    the second derivative of mean motion, 54-61 for BSTAR). Zero renders as
    ``" 00000+0"`` (matching CelesTrak's convention).

    Raises:
        ValueError: If the exponent needs more than one digit.
    """
    if value == 0:
        return " 00000+0"
    sign = "-" if value < 0 else " "
    # From "d.dddde±EE": the five mantissa digits are the significand digits, and the
    # assumed-decimal exponent is one greater (0.ddddd form). %e rounding carries.
    mantissa, exp = f"{abs(value):.4e}".split("e")
    digits = mantissa.replace(".", "")
    exponent = int(exp) + 1
    if abs(exponent) > 9:
        raise ValueError(
            f"Value {value} has an exponent that does not fit the single-digit "
            "TLE exponent field."
        )
    return f"{sign}{digits}{'-' if exponent < 0 else '+'}{abs(exponent)}"


def _checksum(line68: str) -> int:
    """
    Compute the modulo-10 TLE checksum over the first 68 columns of a line.

    Each digit adds its value; each minus sign adds 1; all other characters add 0.
    """
    return (sum(int(c) for c in line68 if c.isdigit()) + line68.count("-")) % 10
