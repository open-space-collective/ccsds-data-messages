"""
KVN adapter: Orbit Ephemeris Message writer.

OEM KVN uses META_START/META_STOP and optionally COVARIANCE_START/COVARIANCE_STOP.
Block delimiter names come from the Delineation private attributes on the domain
model — no strings are hardcoded here.  Keyword names come from FieldMetadata.

Ephemeris data line format (§5.2.4.1):
  epoch x y z x_dot y_dot z_dot [x_ddot y_ddot z_ddot]
  Units: km, km/s, km/s**2 per §7.7.2.1 — NOT displayed on data lines.

Covariance data format (§5.2.5.4):
  Lower-triangular 6×6 matrix, row by row: 1, 2, 3, 4, 5, 6 values per row.
  EPOCH and COV_REF_FRAME are KV pairs before the data rows (§5.2.5.3).

Spec references: §5.2 (OEM structure), §5.2.4 (ephemeris lines),
                 §5.2.5 (covariance), §7.3–7.4, §7.7.2, §7.8.9.
"""
from __future__ import annotations

from pathlib import Path
from typing import TextIO

from orbit_data_messages.io.kvn._utils import emit_block
from orbit_data_messages.io.kvn._utils import emit_kvs
from orbit_data_messages.io.kvn._utils import field_keyword
from orbit_data_messages.io.kvn._utils import format_value
from orbit_data_messages.io.kvn._utils import get_delineation
from orbit_data_messages.models.oem import OEM

# ---------------------------------------------------------------------------
# Covariance field order: the 21 elements of the 6×6 lower triangular matrix
# in the order defined by §5.2.5.4 (upper-left to lower-right, row by row).
# Derived from model_fields declaration order — not hardcoded.
# ---------------------------------------------------------------------------
_CML = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_COV_FIELD_ORDER = [
    fn for fn in _CML.model_fields
    if fn not in ("epoch", "cov_ref_frame")
]

# Keyword names for the two KV fields in CovarianceMatrixLines —
# read from FieldMetadata, not hardcoded.
_EPOCH_KW    = field_keyword(_CML, "epoch")
_COV_REF_KW  = field_keyword(_CML, "cov_ref_frame")

# Row lengths for the 6×6 lower triangular matrix (§5.2.5.4).
_LTM_ROW_LENGTHS = (1, 2, 3, 4, 5, 6)


def _emit_ephemeris_line(
    line: OEM.Segment.EphemerisData.EphemerisDataLine,
    out: TextIO,
) -> None:
    """
    §5.2.4.1 — fixed-order: epoch x y z x_dot y_dot z_dot [x_ddot y_ddot z_ddot].
    §7.7.2.1 — units are km/km/s/km/s**2 but NOT displayed on data lines.
    """
    parts = [
        line.epoch,
        format_value(line.x), format_value(line.y), format_value(line.z),
        format_value(line.x_dot), format_value(line.y_dot), format_value(line.z_dot),
    ]
    if line.x_ddot is not None:
        # §5.2.4.2 — accelerations are all-or-nothing.
        parts += [
            format_value(line.x_ddot),
            format_value(line.y_ddot),
            format_value(line.z_ddot),
        ]
    out.write(" ".join(parts) + "\n")


def _emit_covariance_matrix_lines(
    cml: OEM.Segment.CovarianceMatrix.CovarianceMatrixLines,
    out: TextIO,
) -> None:
    """
    §5.2.5.3 — EPOCH and COV_REF_FRAME as KV pairs.
    §5.2.5.4 — 21 LTM elements written row by row (1/2/3/4/5/6 per row).
    """
    out.write(f"{_EPOCH_KW} = {cml.epoch}\n")
    if cml.cov_ref_frame is not None:
        out.write(f"{_COV_REF_KW} = {format_value(cml.cov_ref_frame)}\n")

    # §5.2.5.4 — lower triangular matrix, upper-left to lower-right.
    values = [getattr(cml, fn) for fn in _COV_FIELD_ORDER]
    idx = 0
    for row_len in _LTM_ROW_LENGTHS:
        row = values[idx: idx + row_len]
        out.write(" ".join(format_value(v) for v in row) + "\n")
        idx += row_len


def _emit_segment(segment: OEM.Segment, out: TextIO) -> None:
    """
    Write one OEM segment: META block + ephemeris data + optional COVARIANCE block.

    §5.2.3.3 — META_START and META_STOP delimit each metadata block.
    §7.8.9   — comments allowed at the beginning of the ephemeris data section
               and at the beginning of the covariance data section.
    §5.2.5.2 — COVARIANCE_START and COVARIANCE_STOP delimit covariance data.
    """
    # Metadata block — delimiters come from Delineation on OEM.Segment.Metadata.
    emit_block(segment.metadata, out)
    out.write("\n")

    # Ephemeris section: optional leading comments (§7.8.9), then data lines.
    ed = segment.ephemeris_data
    if ed.comment:
        for c in ed.comment:
            out.write(f"COMMENT {c}\n")
    for line in ed.ephemeris_data_lines:
        _emit_ephemeris_line(line, out)
    out.write("\n")

    # Optional covariance block (§5.2.5.2).
    if segment.covariance_matrix is not None:
        cm = segment.covariance_matrix
        # Delineation on OEM.Segment.CovarianceMatrix provides the keywords.
        d = get_delineation(type(cm))
        if d:
            out.write(f"{d.start}\n")
        if cm.comment:
            for c in cm.comment:
                out.write(f"COMMENT {c}\n")
        for cml in cm.covariance_matrix_lines:
            _emit_covariance_matrix_lines(cml, out)
        if d:
            out.write(f"{d.stop}\n")
        out.write("\n")


class KVNOEMWriter:
    """
    Writes a validated OEM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OEM, path: Path) -> None:
        with path.open("w", encoding="utf-8") as out:
            # Header (table 5-2).
            emit_block(message.header, out)
            out.write("\n")

            # One or more segments (§5.2.1.2: header + [META + data + optional COV]+).
            for segment in message.segments:
                _emit_segment(segment, out)


OrbitEphemerisMessageKVNWriter = KVNOEMWriter
