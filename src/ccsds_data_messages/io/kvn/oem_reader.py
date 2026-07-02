"""
KVN adapter: Orbit Ephemeris Message reader.

OEM KVN is block-structured: each segment consists of a META block, followed by
ephemeris data lines, followed by an optional COVARIANCE block. Segments repeat.

Spec references:
- Section 5.2 (OEM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.5.10 (date/time format)
- Section 7.7.2 (units)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io._utils import build_keyword_map
from ccsds_data_messages.io._utils import map_kvs
from ccsds_data_messages.io.kvn._utils import block_start_keyword
from ccsds_data_messages.io.kvn._utils import required_block_delimiter_name
from ccsds_data_messages.io.kvn.parser import ODM_MAX_LINE_LENGTH
from ccsds_data_messages.io.kvn.parser import BlankLine
from ccsds_data_messages.io.kvn.parser import BlockStartLine
from ccsds_data_messages.io.kvn.parser import BlockStopLine
from ccsds_data_messages.io.kvn.parser import CommentLine
from ccsds_data_messages.io.kvn.parser import DataLine
from ccsds_data_messages.io.kvn.parser import KeyValueLine
from ccsds_data_messages.io.kvn.parser import parse_kvn
from ccsds_data_messages.models.oem import OEM

if TYPE_CHECKING:
    from pathlib import Path

_CML = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_CML_KW_MAP: dict[str, str] = build_keyword_map(_CML)
_COV_FIELD_ORDER: list[str] = [
    field_name
    for field_name in _CML.model_fields
    if field_name not in ("epoch", "cov_ref_frame")
]
_EPOCH_KEYWORD: str = block_start_keyword(_CML)

_META_BLOCK: str = required_block_delimiter_name(OEM.Segment.Metadata)  # "META"
_COV_BLOCK: str = required_block_delimiter_name(
    OEM.Segment.CovarianceMatrix
)  # "COVARIANCE"


def _parse_ephemeris_line(line: str) -> OEM.Segment.EphemerisData.EphemerisDataLine:
    """
    Parse one OEM ephemeris data line.

    7 tokens = epoch + PV; 10 tokens = epoch + PV + accelerations (section 5.2.4.1-2).
    """
    tokens: list[str] = line.split()
    if len(tokens) not in {7, 10}:
        raise ParseError(
            f"OEM/KVN: an ephemeris line must have 7 tokens (epoch + position + "
            f"velocity) or 10 tokens (with accelerations), got {len(tokens)}: {line!r}"
        )
    epoch, *rest = tokens
    try:
        values = [float(token) for token in rest]
    except ValueError as exc:
        raise ParseError(
            f"OEM/KVN: non-numeric value in ephemeris line: {line!r}"
        ) from exc
    if len(tokens) == 7:
        x, y, z, xd, yd, zd = values
        return OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epoch,
            x=x,
            y=y,
            z=z,
            x_dot=xd,
            y_dot=yd,
            z_dot=zd,
        )
    x, y, z, xd, yd, zd, xdd, ydd, zdd = values
    return OEM.Segment.EphemerisData.EphemerisDataLine(
        epoch=epoch,
        x=x,
        y=y,
        z=z,
        x_dot=xd,
        y_dot=yd,
        z_dot=zd,
        x_ddot=xdd,
        y_ddot=ydd,
        z_ddot=zdd,
    )


class KVNOEMReader:
    """
    Read a KVN-format OEM file and return a validated OEM domain model.

    Satisfies MessageReaderPort structurally. ValidationError is never swallowed.
    """

    def _parse(self, text: str) -> OEM:
        lines = parse_kvn(text, max_line_length=ODM_MAX_LINE_LENGTH)

        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []
        segments: list[OEM.Segment] = []
        pending: list[str] = []
        state = "header"  # header | meta | data | cov

        # Per-segment accumulators (reset after each commit_segment call).
        meta_kvs: dict[str, str] = {}
        meta_comments: list[str] = []
        ephem_lines: list[str] = []
        ephem_comments: list[str] = []

        # Per-covariance-block accumulators.
        cov_block_comments: list[str] = []
        cov_matrices: list[_CML] = []
        cur_cov_kvs: dict[str, str] = {}
        cur_cov_vals: list[float] = []

        def _flush_cov_matrix() -> None:
            nonlocal cur_cov_kvs, cur_cov_vals
            if not cur_cov_kvs:
                return
            if len(cur_cov_vals) != 21:
                raise ParseError(
                    f"OEM/KVN: each covariance matrix must have exactly 21 "
                    f"lower-triangular elements, got {len(cur_cov_vals)}."
                )
            kwargs = map_kvs(cur_cov_kvs, [], _CML)
            for i, fname in enumerate(_COV_FIELD_ORDER):
                kwargs[fname] = cur_cov_vals[i]
            cov_matrices.append(_CML(**kwargs))
            cur_cov_kvs, cur_cov_vals = {}, []

        def _commit_segment(has_cov: bool) -> None:
            nonlocal \
                meta_kvs, \
                meta_comments, \
                ephem_lines, \
                ephem_comments, \
                cov_block_comments, \
                cov_matrices, \
                cur_cov_kvs, \
                cur_cov_vals

            metadata = OEM.Segment.Metadata(
                **map_kvs(meta_kvs, meta_comments, OEM.Segment.Metadata)
            )
            ephemeris_data = OEM.Segment.EphemerisData(
                comment=ephem_comments or None,
                ephemeris_data_lines=[
                    _parse_ephemeris_line(line) for line in ephem_lines
                ],
            )
            covariance_matrix = (
                OEM.Segment.CovarianceMatrix(
                    comment=cov_block_comments or None,
                    covariance_matrix_lines=cov_matrices,
                )
                if has_cov
                else None
            )
            segments.append(
                OEM.Segment(
                    metadata=metadata,
                    ephemeris_data=ephemeris_data,
                    covariance_matrix=covariance_matrix,
                )
            )

            meta_kvs, meta_comments, ephem_lines, ephem_comments = {}, [], [], []
            cov_block_comments, cov_matrices, cur_cov_kvs, cur_cov_vals = [], [], {}, []

        for line in lines:
            if isinstance(line, BlankLine):
                continue

            if isinstance(line, CommentLine):
                pending.append(line.text)
                continue

            if isinstance(line, BlockStartLine):
                if line.block_name == _META_BLOCK:
                    # When the previous segment ended with a COVARIANCE block,
                    # COVARIANCE_STOP already committed it and reset meta_kvs/
                    # ephem_lines to empty (state is left as "data"). Without this
                    # guard, the next segment's META_START would commit a second,
                    # empty segment and fail OEM.Segment.Metadata(**{}) validation.
                    if state == "data" and (meta_kvs or ephem_lines):
                        _commit_segment(has_cov=False)
                    state = "meta"
                    meta_comments = list(pending)
                    pending.clear()
                elif line.block_name == _COV_BLOCK:
                    state = "cov"
                    cov_block_comments = list(pending)
                    pending.clear()
                continue

            if isinstance(line, BlockStopLine):
                if line.block_name == _META_BLOCK:
                    state = "data"
                elif line.block_name == _COV_BLOCK:
                    _flush_cov_matrix()
                    _commit_segment(has_cov=True)
                    state = "data"
                continue

            if isinstance(line, KeyValueLine):
                if state == "header":
                    header_comments.extend(pending)
                    pending.clear()
                    header_kvs[line.keyword] = line.value
                elif state == "meta":
                    meta_comments.extend(pending)
                    pending.clear()
                    meta_kvs[line.keyword] = line.value
                elif state == "cov":
                    if line.keyword == _EPOCH_KEYWORD and cur_cov_kvs:
                        _flush_cov_matrix()
                    cur_cov_kvs[line.keyword] = line.value
                continue

            if isinstance(line, DataLine):
                if state == "data":
                    ephem_comments.extend(pending)
                    pending.clear()
                    ephem_lines.append(line.text)
                elif state == "cov":
                    try:
                        cur_cov_vals.extend(float(t) for t in line.text.split())
                    except ValueError as exc:
                        raise ParseError(
                            f"OEM/KVN: non-numeric value in covariance line: "
                            f"{line.text!r}"
                        ) from exc
                continue

        # Flush the final segment when there's no trailing COVARIANCE block.
        if state == "data" and (meta_kvs or ephem_lines):
            _commit_segment(has_cov=False)

        header = OEM.Header(**map_kvs(header_kvs, header_comments, OEM.Header))
        return OEM(header=header, segments=segments)

    def read(self, path: Path) -> OEM:
        return self._parse(path.read_text(encoding="utf-8"))

    def read_string(self, content: str) -> OEM:
        return self._parse(content)


OrbitEphemerisMessageKVNReader = KVNOEMReader
