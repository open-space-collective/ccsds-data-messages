"""
OEM KVN uses ``META_START/META_STOP`` and optionally ``COVARIANCE_START/COVARIANCE_STOP``.
Block delimiter names come from the Delineation private attributes on the domain
model: no strings are hardcoded here.  Keyword names come from FieldMetadata.

Ephemeris data line format (section 5.2.4.1):
  epoch x y z x_dot y_dot z_dot [x_ddot y_ddot z_ddot]
  Units: km, km/s, km/s**2 per section 7.7.2.1: NOT displayed on data lines.

Covariance data format (section 5.2.5.4):
  Lower-triangular 6 by 6 matrix, row by row: 1, 2, 3, 4, 5, and 6 values per row.
  EPOCH and COV_REF_FRAME are KV pairs before the data rows (section 5.2.5.3).

Spec references:
- Section 5.2 (OEM structure)
- Section 5.2.4 (ephemeris lines)
- Section 5.2.5 (covariance)
- Section 7.3-7.4 (KVN rules)
- Section 7.7.2 (units)
- Section 7.8.9 (comments)
"""
from __future__ import annotations

from pathlib import Path
from typing import TextIO

from orbit_data_messages.io.kvn._utils import block_start_keyword
from orbit_data_messages.io.kvn._utils import emit_block
from orbit_data_messages.io.kvn._utils import emit_kvs
from orbit_data_messages.io.kvn._utils import field_keyword
from orbit_data_messages.io.kvn._utils import format_value
from orbit_data_messages.io.kvn._utils import get_delineation
from orbit_data_messages.io.kvn._utils import Delineation
from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.models.metadata import FieldMetadata
from orbit_data_messages.models.oem import OEM

# Covariance field order: the 21 elements of the 6 by 6 lower triangular matrix
# in the order defined by section 5.2.5.4 (upper-left to lower-right, row by row).
# Derived from model_fields declaration order: not hardcoded.
_CML = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_COV_FIELD_ORDER: list[str] = [
    fn for fn in _CML.model_fields
    if fn not in ("epoch", "cov_ref_frame")
]

# epoch is the block-start sentinel (signals the start of a new covariance matrix).
_EPOCH_KW: str = block_start_keyword(_CML)
# Not a block-start sentinel - used to emit the COV_REF_FRAME KV pair when present.
_COV_REF_KW: str = field_keyword(_CML, "cov_ref_frame")

# Row lengths for the 6×6 lower triangular matrix (section 5.2.5.4).
_LTM_ROW_LENGTHS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)

# Format spec for covariance values: read from the first covariance field's
# FieldMetadata.format_spec; all 21 elements share the same spec.  The spec
# includes the space flag (" .15e") so " ".join(...) yields sign-column layout.
_COV_SPEC: str | None = next(
    (m.format_spec for m in _CML.model_fields[_COV_FIELD_ORDER[0]].metadata
     if isinstance(m, FieldMetadata)),
    None,
)

# Not a block-start sentinel - used only to look up float_formats overrides at runtime
# (all 21 covariance elements share the same spec, so the first field is representative).
_COV_FIRST_KW: str = field_keyword(_CML, _COV_FIELD_ORDER[0])

# Per-field format specs for EphemerisDataLine: read from FieldMetadata.
_EDL: type[OEM.Segment.EphemerisData.EphemerisDataLine] = OEM.Segment.EphemerisData.EphemerisDataLine
_EDL_SPECS: dict[str, str | None] = {
    fn: next((m.format_spec for m in fi.metadata if isinstance(m, FieldMetadata)), None)
    for fn, fi in _EDL.model_fields.items()
}

# CCSDS keywords for EphemerisDataLine fields: used for float_formats lookups.
_EDL_KEYWORDS: dict[str, str | None] = {
    fn: next((m.keyword for m in fi.metadata if isinstance(m, FieldMetadata)), None)
    for fn, fi in _EDL.model_fields.items()
}

# Column width for covariance KV pair alignment (EPOCH=5, COV_REF_FRAME=13).
_COV_KW_WIDTH: int = max(len(_EPOCH_KW), len(_COV_REF_KW))


def _format_ephemeris_parts(
    line: OEM.Segment.EphemerisData.EphemerisDataLine,
    options: WriterOptions | None,
) -> list[str]:
    """
    Return formatted string tokens for one OEM ephemeris data line (section 5.2.4.1).

    Separating formatting from writing enables the two-pass column-alignment
    path: collect all rows' parts first, compute per-column max width, then write.

    Args:
        line (OEM.Segment.EphemerisData.EphemerisDataLine): Ephemeris state to
            format.
        options (WriterOptions | None): Writer options; used to look up
            ``float_formats`` overrides for individual keywords.

    Returns:
        list[str]: Ordered string tokens (epoch, x, y, z, x_dot, y_dot, z_dot,
        and optionally x_ddot, y_ddot, z_ddot).
    """
    def _fmt(field_name: str, value: float) -> str:
        spec: str | None = _EDL_SPECS.get(field_name)
        if options and options.float_formats:
            kw: str | None = _EDL_KEYWORDS.get(field_name)
            if kw and kw in options.float_formats:
                spec: str = options.float_formats[kw]
        return format_value(value, spec)

    parts: list[str] = [
        line.epoch,
        _fmt("x", line.x), _fmt("y", line.y), _fmt("z", line.z),
        _fmt("x_dot", line.x_dot), _fmt("y_dot", line.y_dot), _fmt("z_dot", line.z_dot),
    ]
    if line.x_ddot is not None:
        # Section 5.2.4.2: accelerations are all-or-nothing.
        parts += [
            _fmt("x_ddot", line.x_ddot),
            _fmt("y_ddot", line.y_ddot),
            _fmt("z_ddot", line.z_ddot),
        ]
    return parts


def _emit_ephemeris_line(
    line: OEM.Segment.EphemerisData.EphemerisDataLine,
    out: TextIO,
    *,
    options: WriterOptions | None = None,
) -> None:
    """
    Write one OEM ephemeris line without column alignment (section 5.2.4.1).

    Used when ``options.align_data_columns`` is ``False``; the two-pass
    alignment path calls ``_format_ephemeris_parts`` directly.

    Args:
        line (OEM.Segment.EphemerisData.EphemerisDataLine): Ephemeris state
            to write.
        out (TextIO): Destination text stream.
        options (WriterOptions | None): Writer options. Defaults to None.

    Returns:
        None
    """
    # Section 5.2.4.1: see _format_ephemeris_parts for formatting.
    out.write(" ".join(_format_ephemeris_parts(line, options)) + "\n")


def _emit_covariance_matrix_lines(
    cml: OEM.Segment.CovarianceMatrix.CovarianceMatrixLines,
    out: TextIO,
    *,
    options: WriterOptions | None = None,
) -> None:
    """
    Write one OEM covariance matrix entry: KV header + LTM data rows.

    Writes ``EPOCH`` and, if present, ``COV_REF_FRAME`` as KV pairs (section 5.2.5.3),
    then the 21 lower-triangular elements row by row (1/2/3/4/5/6 per row,
    section 5.2.5.4). The ``' .15e'`` format spec includes the space sign flag so
    positive values get a leading space, matching the sign-column alignment in
    Annex G figure G-13.

    Args:
        cml (OEM.Segment.CovarianceMatrix.CovarianceMatrixLines): Single
            covariance matrix entry to write.
        out (TextIO): Destination text stream.
        options (WriterOptions | None): Writer options. Defaults to None.

    Returns:
        None
    """
    align: bool = options is not None and options.align_keywords
    ew: int = _COV_KW_WIDTH if align else 0  # keyword pad width

    epoch_kw: str = f"{_EPOCH_KW:{ew}}" if align else _EPOCH_KW
    out.write(f"{epoch_kw} = {cml.epoch}\n")
    if cml.cov_ref_frame is not None:
        ref_kw: str = f"{_COV_REF_KW:{ew}}" if align else _COV_REF_KW
        out.write(f"{ref_kw} = {format_value(cml.cov_ref_frame)}\n")

    # Section 5.2.5.4: lower triangular matrix, upper-left to lower-right.
    # The format_spec (" .15e") includes the space flag so " ".join(...) yields
    # sign-column alignment: positive values get a leading space, negative get "-",
    # matching the pattern in spec Annex G figure G-13.
    cov_spec: str | None = _COV_SPEC
    if options and options.float_formats and _COV_FIRST_KW in options.float_formats:
        cov_spec = options.float_formats[_COV_FIRST_KW]

    values: list[float] = [getattr(cml, fn) for fn in _COV_FIELD_ORDER]
    idx: int = 0
    for row_len in _LTM_ROW_LENGTHS:
        row: list[float] = values[idx: idx + row_len]
        if cov_spec is not None:
            out.write(" ".join(format(v, cov_spec) for v in row) + "\n")
        else:
            out.write(" ".join(format_value(v) for v in row) + "\n")
        idx += row_len


def _emit_segment(segment: OEM.Segment, out: TextIO, *, options: WriterOptions | None = None) -> None:
    """
    Write one OEM segment: ``META`` block + ephemeris data + optional ``COVARIANCE`` block.

    Args:
        segment (OEM.Segment): Segment to serialize.
        out (TextIO): Destination text stream.
        options (WriterOptions | None): Writer options. Defaults to None.

    Returns:
        None
    """
    # Section 5.2.3.3: Metadata block delimited by META_START/META_STOP.
    emit_block(segment.metadata, out, options=options)
    out.write("\n")

    # Section 7.8.9: optional leading comments, then ephemeris data lines.
    ephemeris_data: OEM.Segment.EphemerisData = segment.ephemeris_data
    if ephemeris_data.comment:
        for text in ephemeris_data.comment:
            out.write(f"COMMENT {text}\n")
        out.write("\n")  # blank line separating comments from first data line

    if options is not None and options.align_data_columns:
        # Two-pass column alignment (section 5.2.4.3: "at least one space" between items).
        # Pass 1: format all rows, compute max width per column position.
        all_parts: list[list[str]] = [
            _format_ephemeris_parts(line, options)
            for line in ephemeris_data.ephemeris_data_lines
        ]
        col_widths: list[int] = [
            max(len(row[i]) for row in all_parts)
            for i in range(len(all_parts[0]))
        ]
        # Pass 2: write each row with right-justified fixed-width columns.
        for parts in all_parts:
            out.write(" ".join(f"{p:>{w}}" for p, w in zip(parts, col_widths)) + "\n")
    else:
        for line in ephemeris_data.ephemeris_data_lines:
            _emit_ephemeris_line(line, out, options=options)
    out.write("\n")

    # Section 5.2.5.2: optional covariance block delimited by COVARIANCE_START/STOP.
    if segment.covariance_matrix is not None:
        covariance: OEM.Segment.CovarianceMatrix = segment.covariance_matrix
        delineation: Delineation | None = get_delineation(type(covariance))
        if delineation:
            out.write(f"{delineation.start}\n")
        if covariance.comment:
            for text in covariance.comment:
                out.write(f"COMMENT {text}\n")
        for i, cml in enumerate(covariance.covariance_matrix_lines):
            if i > 0:
                out.write("\n")  # blank line between consecutive matrices
            _emit_covariance_matrix_lines(cml, out, options=options)
        if delineation:
            out.write(f"{delineation.stop}\n")
        out.write("\n")


class KVNOEMWriter:
    """
    Write a validated OEM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OEM, path: Path, *, options: WriterOptions | None = None) -> None:
        """
        Serialize a validated OEM domain model to a KVN file at path.

        Args:
            message (OEM): Validated OEM instance to serialize.
            path (Path): Destination file. Created or overwritten.
            options (WriterOptions | None): Formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        with path.open("w", encoding="utf-8") as out:
            # Header (table 5-2).
            emit_block(message.header, out, options=options)
            out.write("\n")

            # One or more segments (section 5.2.1.2: header + [META + data + optional COV]+).
            for segment in message.segments:
                _emit_segment(segment, out, options=options)


OrbitEphemerisMessageKVNWriter = KVNOEMWriter
