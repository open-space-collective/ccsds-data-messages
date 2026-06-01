"""Annotation types for attaching CCSDS keyword metadata to Pydantic model fields."""
from __future__ import annotations


class Delineation:
    """Holds the START/STOP keyword pair that delimits a named block in KVN or XML format.

    Instances are stored as ``ClassVar`` attributes on nested Pydantic model classes
    (e.g. ``OEM.Segment.Metadata``) so that I/O adapters can read the correct delimiter
    strings by introspection rather than hardcoding them.

    Attributes:
        start (str): The opening keyword, e.g. ``"META_START"``.
        stop (str): The closing keyword, e.g. ``"META_STOP"``.
    """

    def __init__(
        self,
        start: str,
        stop: str,
    ) -> None:
        """Create a block delimiter pair.

        Args:
            start (str): The opening keyword, e.g. ``"META_START"``.
            stop (str): The closing keyword, e.g. ``"META_STOP"``.
        """
        self.start: str = start
        self.stop: str = stop

    def __str__(self) -> str:
        """Return the delimiter pair as ``"START / STOP"``.

        Returns:
            str: The opening and closing keywords separated by `` / ``.
        """
        return f"{self.start} / {self.stop}"


class FieldMetadata:
    """Annotation attached to a Pydantic field to record its CCSDS keyword name and optional unit.

    Used in ``Annotated[type, FieldMetadata(keyword=..., units=...)]`` field declarations so
    that I/O adapters can discover keyword names and units by introspecting
    ``field_info.metadata`` rather than hardcoding keyword strings.

    Attributes:
        keyword (str): The CCSDS keyword string.
        units (str | None): Physical unit string, or ``None`` for dimensionless fields.
        delineation (Delineation | None): Optional block delimiter pair.
        format_spec (str | None): Python format-spec string for float serialization.
    """

    def __init__(
        self,
        keyword: str,
        units: str | None = None,
        delineation: Delineation | None = None,
        format_spec: str | None = None,
    ) -> None:
        """Create field metadata for a CCSDS keyword.

        Args:
            keyword (str): The CCSDS keyword string, e.g. ``"OBJECT_NAME"``.
            units (str | None): Physical unit string, e.g. ``"km"`` or ``"km/s"``.
                ``None`` for dimensionless or string fields.
            delineation (Delineation | None): Optional block delimiter pair. Rarely
                used directly on a field; prefer the ``ClassVar`` pattern on nested
                block classes.
            format_spec (str | None): Python format-spec string (mini-language) for
                serializing float values, e.g. ``".3f"`` or ``" .15e"``. ``None``
                falls back to ``repr()``. Adapters read this to format numeric output.
        """
        self.keyword: str = keyword
        self.units: str | None = units
        self.delineation: Delineation | None = delineation
        self.format_spec: str | None = format_spec

    @property
    def delineation_str(self) -> str:
        """Return the delineation as ``"START / STOP"``, or an empty string if absent.

        Returns:
            str: The delineation pair as ``"START / STOP"``, or ``""`` if not set.
        """
        return f"{self.delineation.start} / {self.delineation.stop}" if self.delineation else ""

    def __str__(self) -> str:
        """Return a human-readable representation of the field metadata.

        Returns:
            str: Keyword with optional unit and delineation info appended.
        """
        return f"{self.keyword}{f' [{self.units}]' if self.units else ''}{f' ({self.delineation_str})' if self.delineation else ''}"
