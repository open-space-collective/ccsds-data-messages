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
    Reject version strings that are not in '3.y' format (CCSDS 502.0-B-3).

    Args:
        value (str): The version string to validate.
        field_name (str): Field name used in the error message.

    Raises:
        ValueError: If value does not match '3.y' (e.g. '3.0').
    """
    if not re.fullmatch(r"3\.\d+", value):
        raise ValueError(
            f"{field_name} must be in '3.y' form (CCSDS 502.0-B-3), e.g. '3.0', got {value!r}"
        )
    return value


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
