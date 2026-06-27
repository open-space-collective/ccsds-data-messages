# SPDX-License-Identifier: Apache-2.0

"""
Annotation types for attaching CCSDS keyword metadata to Pydantic model fields.

Provides a single canonical implementation for the two CCSDS delineation keywords, e.g.:
    - ``COVARIANCE_START`` / ``COVARIANCE_STOP``: signals the start/end of a covariance matrix block.
    - ``META_START`` / ``META_STOP``: signals the start/end of a metadata block.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Delineation:
    """
    Holds the start/stop keyword pair that delimits a named block in KVN or XML format.

    Instances are stored as ``ClassVar`` attributes on nested Pydantic model classes
    (e.g. ``OEM.Segment.Metadata``) so that I/O adapters can read the correct delimiter
    strings by introspection rather than hardcoding them.
    """

    start: str
    stop: str

    def __str__(self) -> str:
        return f"{self.start} / {self.stop}"


@dataclass(frozen=True)
class FieldMetadata:
    """
    Annotation attached to a Pydantic field, carrying its CCSDS keyword and unit.

    Used in ``Annotated[type, FieldMetadata(keyword=..., units=...)]`` field declarations so
    that I/O adapters can discover keyword names and units by introspecting
    ``field_info.metadata`` rather than hardcoding keyword strings.

    Attributes:
        keyword (str): The CCSDS keyword string.
        units (str | None): Physical unit string, or ``None`` for dimensionless fields.
        delineation (Delineation | None): Optional block delimiter pair.
        format_spec (str | None): Python format-spec string for float serialization.
        block_start (bool): ``True`` when this keyword signals the start of a new
            instance of a repeating block (e.g. a new maneuver or covariance matrix).
    """

    keyword: str
    units: str | None = None
    delineation: Delineation | None = None
    format_spec: str | None = None
    block_start: bool = False

    @property
    def delineation_str(self) -> str:
        """Return the delineation as ``"START / STOP"``, or an empty string if absent."""
        if not self.delineation:
            return ""
        return f"{self.delineation.start} / {self.delineation.stop}"

    def __str__(self) -> str:
        """
        Return a human-readable representation of the field metadata.

        Examples:
            >>> str(FieldMetadata("X", units="km", delineation=Delineation("COVARIANCE_START", "COVARIANCE_STOP")))
            "X [km] (COVARIANCE_START / COVARIANCE_STOP)"
            >>> str(FieldMetadata("OBJECT_NAME"))
            "OBJECT_NAME"
        """
        units_part: str = f" [{self.units}]" if self.units else ""
        delim_part: str = f" ({self.delineation_str})" if self.delineation else ""
        return f"{self.keyword}{units_part}{delim_part}"
