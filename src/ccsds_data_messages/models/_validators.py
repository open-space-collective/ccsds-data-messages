# SPDX-License-Identifier: Apache-2.0

"""
Shared validator helper functions for CCSDS data message blocks.
"""

from __future__ import annotations

import re

from ._epoch import validate_ccsds_date
from ._epoch import validate_time_tag


def _validate_comment(value: list[str] | None) -> list[str] | None:
    """
    Reject an empty list; allow None or a non-empty list.

    Raises:
        ValueError: If value is an empty list.
    """
    if value is not None and not value:
        raise ValueError("comment must be None or a non-empty list of strings.")
    return value


def _validate_version_format(value: str, field_name: str = "version") -> str:
    """
    Reject version strings that are not in '3.y' format (used for OCM, section 7.9.1).

    Args:
        value (str): The version string to validate.
        field_name (str): Field name used in the error message.

    Raises:
        ValueError: If value does not match '3.y' (e.g. '3.0').
    """
    # Accept 3.y broadly: OCM was introduced at 3.0 in 502.0-B-3 (section 7.9.1), but
    # future Blue Book issues may define minor revisions (3.1, etc.). Unlike
    # OPM/OMM/OEM, which have a closed historical set of sanctioned versions,
    # OCM has no such set yet, so the check stays open-ended on the minor digit.
    if not re.fullmatch(r"3\.\d+", value):
        raise ValueError(
            f"{field_name} must be in '3.y' form (CCSDS 502.0-B-3), e.g. '3.0', got {value!r}"
        )
    return value


_OPM_VALID_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0", "3.0"})
_OMM_VALID_VERSIONS: frozenset[str] = frozenset({"2.0", "3.0"})
_OEM_VALID_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0", "3.0"})


def _validate_version_in_set(value: str, allowed: frozenset[str], field_name: str) -> str:
    if not re.fullmatch(r"\d+\.\d+", value):
        raise ValueError(f"{field_name} must be in 'x.y' form, got {value!r}")
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}, got {value!r}")
    return value


def _validate_opm_version(value: str) -> str:
    """Section 7.9.1: OPM valid versions are {1.0, 2.0, 3.0}."""
    return _validate_version_in_set(value, _OPM_VALID_VERSIONS, "CCSDS_OPM_VERS")


def _validate_omm_version(value: str) -> str:
    """Section 7.9.1: OMM valid versions are {2.0, 3.0}."""
    return _validate_version_in_set(value, _OMM_VALID_VERSIONS, "CCSDS_OMM_VERS")


def _validate_oem_version(value: str) -> str:
    """Section 7.9.1: OEM valid versions are {1.0, 2.0, 3.0}."""
    return _validate_version_in_set(value, _OEM_VALID_VERSIONS, "CCSDS_OEM_VERS")


def _validate_optional_ccsds_date(v: str | None) -> str | None:
    """Validate a CCSDS absolute date string when present; pass None through."""
    return validate_ccsds_date(v) if v is not None else v


def _validate_optional_time_tag(v: str | None) -> str | None:
    """Validate a CCSDS date or relative time string when present; pass None through."""
    return validate_time_tag(v) if v is not None else v


def _validate_negative_mass(v: float | None) -> float | None:
    """
    Reject non-negative mass deltas; pass None through.

    Raises:
        ValueError: If v is not None and v >= 0.
    """
    if v is not None and v >= 0:
        raise ValueError("MAN_DELTA_MASS must be negative.")
    return v


_UN_OOSA_DESIGNATOR_RE: re.Pattern[str] = re.compile(r"\d{4}-\d{3}[A-Z]+")


def _validate_un_oosa_designator(value: str, field_name: str = "object_id") -> str:
    """
    Enforce the UN Office of Outer Space Affairs designator index format.

    Format: YYYY-NNNP{PP} (4-digit launch year, 3-digit launch serial number,
    at least one capital letter for the launched piece). ``UNKNOWN`` is always
    accepted, per the spec's own escape value for undisclosed/unlisted objects.

    Raises:
        ValueError: If value is neither ``UNKNOWN`` nor a valid designator.
    """
    if value != "UNKNOWN" and not _UN_OOSA_DESIGNATOR_RE.fullmatch(value):
        raise ValueError(
            f"{field_name} must be in UN OOSA designator index format 'YYYY-NNNP{{PP}}' "
            f"(e.g. '1998-067A') or 'UNKNOWN', got {value!r}."
        )
    return value
