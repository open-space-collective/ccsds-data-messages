"""
KVN adapter: Orbit Ephemeris Message writer.

OEM KVN uses META_START/META_STOP and optionally COVARIANCE_START/COVARIANCE_STOP.
Block delimiter names come from the Delineation private attributes on the domain
model: no strings are hardcoded here.

Ephemeris data line format (section 5.2.4.1):
  epoch x y z x_dot y_dot z_dot [x_ddot y_ddot z_ddot]
  Units: km, km/s, km/s**2 per section 7.7.2.1 — NOT displayed on data lines.

Covariance data format (section 5.2.5.4):
  Lower-triangular 6×6 matrix, row by row: 1, 2, 3, 4, 5, and 6 values per row.
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

import io
from typing import TYPE_CHECKING

from ccsds_data_messages.io.kvn._utils import (
    SupportsWrite,
    block_start_keyword,
    emit_block,
    field_keyword,
    format_value,
    get_delineation,
    guard_lines,
)
from ccsds_data_messages.io.kvn.parser import ODM_MAX_LINE_LENGTH
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models._fields import FieldMetadata
from ccsds_data_messages.models.oem import OEM

if TYPE_CHECKING:
    from pathlib import Path

# Block delimiter for COVARIANCE — derived from model, not hardcoded.
_COVARIANCE_DELIMITER = get_delineation(OEM.Segment.CovarianceMatrix)

# Covariance matrix field setup.
_COVARIANCE_MATRIX_LINES = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_COV_FIELD_ORDER: list[str] = [
    fn
    for fn in _COVARIANCE_MATRIX_LINES.model_fields
    if fn not in ("epoch", "cov_ref_frame")
]
_EPOCH_KEYWORD: str = block_start_keyword(_COVARIANCE_MATRIX_LINES)
_COVARIANCE_REF_FRAME_KEYWORD: str = field_keyword(
    _COVARIANCE_MATRIX_LINES, "cov_ref_frame"
)
_COVARIANCE_KEYWORD_WIDTH: int = max(
    len(_EPOCH_KEYWORD), len(_COVARIANCE_REF_FRAME_KEYWORD)
)
_LTM_ROW_LENGTHS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)

# Format spec for covariance values: shared by all 21 lower-triangular elements.
_COVARIANCE_FORMAT_SPEC: str | None = next(
    (
        m.format_spec
        for m in _COVARIANCE_MATRIX_LINES.model_fields[_COV_FIELD_ORDER[0]].metadata
        if isinstance(m, FieldMetadata)
    ),
    None,
)
_COV_FIRST_KW: str = field_keyword(_COVARIANCE_MATRIX_LINES, _COV_FIELD_ORDER[0])

# Per-field format specs and keywords for EphemerisDataLine.
_EPHEMERIS_DATA_LINE = OEM.Segment.EphemerisData.EphemerisDataLine
_EPHEMERIS_DATA_LINE_FORMAT_SPECS: dict[str, str | None] = {
    fn: next((m.format_spec for m in fi.metadata if isinstance(m, FieldMetadata)), None)
    for fn, fi in _EPHEMERIS_DATA_LINE.model_fields.items()
}
_EPHEMERIS_DATA_LINE_KEYWORDS: dict[str, str | None] = {
    fn: next((m.keyword for m in fi.metadata if isinstance(m, FieldMetadata)), None)
    for fn, fi in _EPHEMERIS_DATA_LINE.model_fields.items()
}


def _format_ephemeris_parts(
    line: OEM.Segment.EphemerisData.EphemerisDataLine,
    options: WriterOptions | None,
) -> list[str]:
    """Return formatted string tokens for one OEM ephemeris data line (section 5.2.4.1)."""

    def _fmt(field_name: str, value: float) -> str:
        spec: str | None = _EPHEMERIS_DATA_LINE_FORMAT_SPECS.get(field_name)
        if options and options.float_formats:
            kw = _EPHEMERIS_DATA_LINE_KEYWORDS.get(field_name)
            if kw and kw in options.float_formats:
                spec = options.float_formats[kw]
        return format_value(value, spec)

    parts = [
        line.epoch,
        _fmt("x", line.x),
        _fmt("y", line.y),
        _fmt("z", line.z),
        _fmt("x_dot", line.x_dot),
        _fmt("y_dot", line.y_dot),
        _fmt("z_dot", line.z_dot),
    ]
    # validate_acceleration_all_or_nothing (models/oem.py) guarantees these three are
    # either all None or all non-None; checking all three (not just x_ddot) narrows
    # each individually instead of relying on that invariant implicitly.
    if line.x_ddot is not None and line.y_ddot is not None and line.z_ddot is not None:
        parts += [
            _fmt("x_ddot", line.x_ddot),
            _fmt("y_ddot", line.y_ddot),
            _fmt("z_ddot", line.z_ddot),
        ]
    return parts


def _emit_covariance_matrix_lines(
    cml: OEM.Segment.CovarianceMatrix.CovarianceMatrixLines,
    out: SupportsWrite,
    *,
    options: WriterOptions | None = None,
) -> None:
    """Write EPOCH/COV_REF_FRAME KV pairs then the 21 lower-triangular elements (section 5.2.5.3-4)."""
    align = options is not None and options.align_keywords
    pad = _COVARIANCE_KEYWORD_WIDTH if align else 0

    out.write(f"{_EPOCH_KEYWORD:{pad}} = {cml.epoch}\n")
    if cml.cov_ref_frame is not None:
        out.write(
            f"{_COVARIANCE_REF_FRAME_KEYWORD:{pad}} = {format_value(cml.cov_ref_frame)}\n"
        )

    cov_spec = _COVARIANCE_FORMAT_SPEC
    if options and options.float_formats and _COV_FIRST_KW in options.float_formats:
        cov_spec = options.float_formats[_COV_FIRST_KW]

    values = [getattr(cml, fn) for fn in _COV_FIELD_ORDER]
    idx = 0
    for row_len in _LTM_ROW_LENGTHS:
        row = values[idx : idx + row_len]
        if cov_spec is not None:
            out.write(" ".join(format(v, cov_spec) for v in row) + "\n")
        else:
            out.write(" ".join(format_value(v) for v in row) + "\n")
        idx += row_len


def _emit_segment(
    segment: OEM.Segment,
    out: SupportsWrite,
    *,
    options: WriterOptions | None = None,
) -> None:
    """Write one OEM segment: META block + ephemeris data + optional COVARIANCE block."""
    emit_block(segment.metadata, out, options=options)
    out.write("\n")

    ephemeris_data = segment.ephemeris_data
    if ephemeris_data.comment:
        out.writelines(f"COMMENT {text}\n" for text in ephemeris_data.comment)
        out.write("\n")

    if options is not None and options.align_data_columns:
        all_parts = [
            _format_ephemeris_parts(line, options)
            for line in ephemeris_data.ephemeris_data_lines
        ]
        # Derive each column's width only from rows that have that column: lines
        # without accelerations (7 tokens) are shorter than lines with them (10),
        # and indexing off all_parts[0] alone would silently truncate longer rows
        # via the zip() below once a column index exceeds the first row's length.
        max_cols = max((len(row) for row in all_parts), default=0)
        col_widths = [
            max(len(row[i]) for row in all_parts if i < len(row)) for i in range(max_cols)
        ]
        # strict=False is intentional here: a 7-token row is meant to zip with only
        # the first 7 of col_widths's (up to) 10 entries - see the comment above.
        out.writelines(
            " ".join(f"{p:>{w}}" for p, w in zip(parts, col_widths))  # noqa: B905
            + "\n"
            for parts in all_parts
        )
    else:
        out.writelines(
            " ".join(_format_ephemeris_parts(line, options)) + "\n"
            for line in ephemeris_data.ephemeris_data_lines
        )
    out.write("\n")

    if segment.covariance_matrix is not None:
        cov = segment.covariance_matrix
        if _COVARIANCE_DELIMITER:
            out.write(f"{_COVARIANCE_DELIMITER.start}\n")
        if cov.comment:
            out.writelines(f"COMMENT {text}\n" for text in cov.comment)
        for i, cml in enumerate(cov.covariance_matrix_lines):
            if i > 0:
                out.write("\n")
            _emit_covariance_matrix_lines(cml, out, options=options)
        if _COVARIANCE_DELIMITER:
            out.write(f"{_COVARIANCE_DELIMITER.stop}\n")
        out.write("\n")


class KVNOEMWriter:
    """
    Write a validated OEM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def _write(
        self, message: OEM, out: SupportsWrite, *, options: WriterOptions | None = None
    ) -> None:
        out = guard_lines(out, max_line_length=ODM_MAX_LINE_LENGTH)
        emit_block(message.header, out, options=options)
        out.write("\n")

        for segment in message.segments:
            _emit_segment(segment, out, options=options)

    def write(
        self, message: OEM, path: Path, *, options: WriterOptions | None = None
    ) -> None:
        with path.open("w", encoding="utf-8") as out:
            self._write(message, out, options=options)

    def write_string(self, message: OEM, *, options: WriterOptions | None = None) -> str:
        with io.StringIO() as buffer:
            self._write(message, buffer, options=options)
            return buffer.getvalue()


OrbitEphemerisMessageKVNWriter = KVNOEMWriter
