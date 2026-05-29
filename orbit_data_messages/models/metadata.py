"""Annotation types for attaching CCSDS keyword metadata to Pydantic model fields."""


class Delineation:
    """Holds the START/STOP keyword pair that delimits a named block in KVN or XML format.

    Instances are stored as ``ClassVar`` attributes on nested Pydantic model classes
    (e.g. ``OEM.Segment.Metadata``) so that I/O adapters can read the correct delimiter
    strings by introspection rather than hardcoding them.
    """

    def __init__(
        self,
        start: str,
        stop: str,
    ) -> None:
        """Creates a block delimiter pair.

        Args:
            start: The opening keyword, e.g. ``"META_START"``.
            stop: The closing keyword, e.g. ``"META_STOP"``.
        """
        self.start = start
        self.stop = stop

    def __str__(self) -> str:
        return f"{self.start} / {self.stop}"


class FieldMetadata:
    """Annotation attached to a Pydantic field to record its CCSDS keyword name and optional unit.

    Used in ``Annotated[type, FieldMetadata(keyword=..., units=...)]`` field declarations so
    that I/O adapters can discover keyword names and units by introspecting
    ``field_info.metadata`` rather than hardcoding keyword strings.
    """

    def __init__(
        self,
        keyword: str,
        units: str | None = None,
        delineation: Delineation | None = None,
        format_spec: str | None = None,
    ) -> None:
        """Creates field metadata for a CCSDS keyword.

        Args:
            keyword: The CCSDS keyword string, e.g. ``"OBJECT_NAME"``.
            units: Physical unit string, e.g. ``"km"`` or ``"km/s"``. ``None`` for
                dimensionless or string fields.
            delineation: Optional block delimiter pair. Rarely used directly on a
                field; prefer the ``ClassVar`` pattern on nested block classes.
            format_spec: Python format-spec string (mini-language) for serializing
                float values, e.g. ``".3f"`` or ``" .10e"``. ``None`` falls back to
                ``repr()``.  Adapters read this to format numeric output correctly.
        """
        self.keyword = keyword
        self.units = units
        self.delineation = delineation
        self.format_spec = format_spec

    @property
    def delineation_str(self) -> str:
        """Returns the delineation as ``"START / STOP"``, or an empty string if absent."""
        return f"{self.delineation.start} / {self.delineation.stop}" if self.delineation else ""

    def __str__(self) -> str:
        return f"{self.keyword}{f' [{self.units}]' if self.units else ''}{f' ({self.delineation_str})' if self.delineation else ''}"
