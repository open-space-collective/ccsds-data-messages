"""Runtime formatting options for CCSDS ODM writers."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass
class WriterOptions:
    """Formatting options threaded through all KVN and XML writers.

    Defaults produce human-readable, spec-recommended output.  Pass an instance
    as ``Writer.write(..., options=WriterOptions(...))`` to customize behavior.

    All changes from these options are spec-compliant:

    - ``include_units`` follows §8.13.6 (XML attributes for units) and Table 8-6.
    - ``align_keywords`` is valid per §7.4.5 (whitespace around keywords is insignificant).
    - ``float_formats`` overrides must use valid numeric formats per §7.5.5–7.5.7
      (fixed-point or scientific, ≤16 significant digits).
    """

    # ── XML ─────────────────────────────────────────────────────────────────

    include_units: bool = True
    """Add ``units=""`` attributes to numeric XML elements (e.g. ``<X units="km">``).

    §8.13.6 states "XML attributes shall be used to explicitly define the units";
    §8.10.18 allows them to be omitted.  Default ``True`` follows §8.13.6 and
    the example tables (8-2, 8-4, 8-6, 8-7).
    Set ``False`` for minimal XML without unit annotations.
    """

    # ── KVN ─────────────────────────────────────────────────────────────────

    align_keywords: bool = True
    """Right-pad KVN keywords within each block so ``=`` signs align in a column.

    Block-local: each block aligns independently to its own longest keyword.
    Purely cosmetic — §7.4.5 states whitespace around keywords is insignificant.

    Example (align_keywords=True)::

        OBJECT_NAME          = IMPERIAL SHUTTLE TYDIRIUM
        OBJECT_ID            = 2983-101A
        INTERPOLATION_DEGREE = 7

    Example (align_keywords=False, compact)::

        OBJECT_NAME = IMPERIAL SHUTTLE TYDIRIUM
        OBJECT_ID = 2983-101A
        INTERPOLATION_DEGREE = 7
    """

    align_data_columns: bool = True
    """Right-justify OEM ephemeris data columns so all rows share the same column widths.

    Two-pass: all lines in a segment are formatted first, then written with per-column
    fixed widths (rightmost character of each value aligns across rows).
    Purely cosmetic — §5.2.4.3 only requires "at least one space between items".

    Example (align_data_columns=True)::

        2983-10-06T04:00:00.000Z  1917.000     0.000     0.000  -0.00000   1.59910   0.12793
        2983-10-06T04:05:00.000Z  1857.286   474.738    37.979  -0.39601   1.54929   0.12394

    Example (align_data_columns=False, compact)::

        2983-10-06T04:00:00.000Z  1917.000  0.000  0.000 -0.00000  1.59910  0.12793
        2983-10-06T04:05:00.000Z  1857.286  474.738  37.979 -0.39601  1.54929  0.12394
    """

    # ── Float formatting ─────────────────────────────────────────────────────

    float_formats: dict[str, str] = field(default_factory=dict)
    """Per-keyword format-spec overrides, keyed by CCSDS keyword string.

    Overrides the ``FieldMetadata.format_spec`` baked into the domain model.
    Keys are uppercase CCSDS keyword strings (the same names used in KVN and
    as XML element names, e.g. ``"X"``, ``"CX_X"``, ``"MEAN_MOTION"``).

    Uses Python's format mini-language.  The ``" "`` (space) flag is
    recommended for columns that mix positive and negative values — it gives
    positive values a leading space, aligning the sign character across rows.

    Examples::

        # Higher-precision position and velocity in an OEM:
        WriterOptions(float_formats={
            "X": " .6f", "Y": " .6f", "Z": " .6f",
            "X_DOT": " .9f", "Y_DOT": " .9f", "Z_DOT": " .9f",
        })

        # Full IEEE-754 double precision (16 sig digits) for specific fields:
        WriterOptions(float_formats={"CX_X": " .15e"})

        # Suppress sign-column alignment on a field:
        WriterOptions(float_formats={"X": ".3f"})
    """
