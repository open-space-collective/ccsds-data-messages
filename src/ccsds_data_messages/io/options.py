# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class WriterOptions:
    """
    Formatting options for all ``CCSDSDataMessage`` file writers.

    Defaults produce human-readable, spec-recommended output. Pass an instance
    as ``Writer.write(..., options=WriterOptions(...))`` to customize behavior.

    All changes from these options are spec-compliant:

    - ``include_units`` follows section 8.13.6 (XML attributes for units) and Table 8-6.
    - ``align_keywords`` is valid per section 7.4.5 (whitespace around keywords is insignificant).
    - ``float_formats`` overrides must use valid numeric formats per section 7.5.5-7.5.7
      (fixed-point or scientific, less than or equal to 16 significant digits).
    """

    # Only relevant for XML output.
    include_units: bool = True
    """
    Add ``units=""`` attributes to numeric XML elements (e.g. ``<X units="km">``).

    Section 8.13.6 states "XML attributes shall be used to explicitly define the units".
    Section 8.10.18 allows them to be omitted. Default ``True`` follows section 8.13.6 and
    the example tables (8-2, 8-4, 8-6, 8-7) in the spec. Set ``False`` for minimal XML
    output without unit annotations.
    """

    # Only relevant for KVN output.
    align_keywords: bool = True
    """
    Right-pad KVN keywords within each block so the ``=`` signs align in a column.

    Block-local: each block aligns independently to the longest keyword in that block.
    Purely cosmetic: section 7.4.5 states whitespace around keywords is insignificant.

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
    """
    Right-justify OEM ephemeris data columns so all rows have the same column widths.

    Note: this option applies only to OEM KVN ephemeris lines. OCM trajectory, covariance,
    and maneuver data lines are written verbatim regardless of this setting.

    Two-pass: all lines in a segment are formatted first, then written with per-column
    fixed widths (the rightmost character of each value aligns across rows). Section 5.2.4.3
    only requires "at least one space between items".

    Example (align_data_columns=True)::

        2983-10-06T04:00:00.000Z  1917.000     0.000     0.000  -0.00000   1.59910   0.12793
        2983-10-06T04:05:00.000Z  1857.286   474.738    37.979  -0.39601   1.54929   0.12394

    Example (align_data_columns=False, compact)::

        2983-10-06T04:00:00.000Z  1917.000  0.000  0.000 -0.00000  1.59910  0.12793
        2983-10-06T04:05:00.000Z  1857.286  474.738  37.979 -0.39601  1.54929  0.12394
    """

    # Only relevant for KVN output.
    float_formats: dict[str, str] = field(default_factory=dict)
    """
    Per-keyword format-spec overrides, keyed by CCSDS keyword string
    (e.g. ``"X"``, ``"CX_X"``, ``"MEAN_MOTION"``).

    Overrides the ``FieldMetadata.format_spec`` baked into the domain model. Uses Python's
    format mini-language. The ``" "`` (space) flag is recommended for columns that mix
    positive and negative values: it gives positive values a leading space, aligning the
    sign character across rows.

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
