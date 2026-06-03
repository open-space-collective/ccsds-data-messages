"""
Implements ``MessageReaderPort`` for the KVN format.  All keyword strings are read
from ``FieldMetadata`` annotations on the OEM domain model; none are hardcoded.
Block delimiter names (``META``, ``COVARIANCE``) are derived from the
``Delineation`` private attributes on the relevant nested classes.

Spec references:
- Section 5.2 (OEM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.5.10 (date/time format)
- Section 7.7.2 (units)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from orbit_data_messages.io.kvn._utils import block_delimiter_name
from orbit_data_messages.io.kvn._utils import block_start_keyword
from orbit_data_messages.io.kvn._utils import build_keyword_map
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.io.kvn.parser import split_blocks
from orbit_data_messages.models.oem import OEM


# Covariance field order and epoch keyword: derived from the domain model,
# not hardcoded.
#
# Section 5.2.5.4 defines the LTM order; the model fields are declared in that same
# order so we can read it from ``model_fields``.  We skip ``epoch`` and
# ``cov_ref_frame`` (the two header KV fields) to get only the 21 matrix fields.
_CML = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_CML_KW_MAP: dict[str, str] = build_keyword_map(_CML)
# Python field names in LTM order (preserves Pydantic field declaration order).
_COV_FIELD_ORDER: list[str] = [
    field_name for field_name in _CML.model_fields
    if field_name not in ("epoch", "cov_ref_frame")
]
# The KVN keyword that signals the start of a new covariance matrix block:
# discovered via ``block_start=True`` on ``CovarianceMatrixLines.epoch``.
_EPOCH_KEYWORD: str = block_start_keyword(_CML)


def _parse_ephemeris_line(line: str) -> OEM.Segment.EphemerisData.EphemerisDataLine:
    """
    Parse one OEM ephemeris data line into a validated ``OEM.Segment.EphemerisData.EphemerisDataLine`` model.

    Each line begins with an epoch followed by position, velocity, and
    optionally acceleration components (section 5.2.4.1). Accelerations are
    all-or-nothing (section 5.2.4.2): 7 tokens give ``epoch + PV``; 10 tokens give
    ``epoch + PV + accelerations``.

    Args:
        line (str): A single raw ephemeris data line from the KVN file.

    Returns:
        OEM.Segment.EphemerisData.EphemerisDataLine: Parsed and validated
        ephemeris state.

    Raises:
        ValueError: If the line does not contain exactly 7 or 10 tokens.
    """
    epoch: str
    x: str
    y: str
    z: str
    xd: str
    yd: str
    zd: str
    xdd: str
    ydd: str
    zdd: str
    tokens: list[str] = line.split()
    if len(tokens) == 7:
        epoch, x, y, z, xd, yd, zd = tokens
        return OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epoch,
            x=float(x),
            y=float(y),
            z=float(z),
            x_dot=float(xd),
            y_dot=float(yd),
            z_dot=float(zd),
        )
    if len(tokens) == 10:
        epoch, x, y, z, xd, yd, zd, xdd, ydd, zdd = tokens
        return OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epoch,
            x=float(x),
            y=float(y),
            z=float(z),
            x_dot=float(xd),
            y_dot=float(yd),
            z_dot=float(zd),
            x_ddot=float(xdd),
            y_ddot=float(ydd),
            z_ddot=float(zdd),
        )
    raise ValueError(
        f"An OEM ephemeris line must have 7 tokens (epoch + position + velocity) "
        f"or 10 tokens (with accelerations), got {len(tokens)}: {line!r}"
    )


def _parse_covariance_block(block: dict[str, Any]) -> OEM.Segment.CovarianceMatrix:
    """
    Parse a KVN ``COVARIANCE`` block into a validated ``OEM.Segment.CovarianceMatrix`` model.

    A block may contain one or more matrices, each introduced by an ``EPOCH``
    KV pair followed by data lines containing the LTM rows (section 5.2.5.4).
    ``ordered_items`` is used rather than the flat ``kvs`` dict so that repeated
    ``EPOCH`` keys are handled correctly.

    Args:
        block (dict[str, Any]): Parsed block dict from ``split_blocks()``,
            containing ``ordered_items``, ``kvs``, and ``comments``.

    Returns:
        OEM.Segment.CovarianceMatrix: Validated covariance matrix model
        containing one ``CovarianceMatrixLines`` entry per epoch.

    Raises:
        ValueError: If any individual matrix does not contain exactly 21 LTM
            elements (section 5.2.5.4).
    """
    comments: list[str] = block.get("comments", [])

    # Walk ordered_items to group [kv* data*]+ into individual matrices.
    matrices: list[OEM.Segment.CovarianceMatrix.CovarianceMatrixLines] = []
    current_kvs: dict[str, str] = {}
    current_values: list[float] = []  # Section 5.2.5.4, 5.2.5.5: data line contains whitespace-separated floats.

    # Nested function (also known as an inner function) used to
    # encapsulate helper logic within ``_parse_covariance_block()``.
    def _flush_matrix() -> None:
        """
        Flush the current covariance matrix to the list of matrices.
        """
        if not current_kvs and not current_values:
            return
        if len(current_values) != 21:
            raise ValueError(
                f"Each OEM covariance matrix must have exactly 21 lower-triangular "
                f"elements, got {len(current_values)}."
            )
        kwargs: dict[str, Any] = map_kvs(
            current_kvs,
            comments,
            OEM.Segment.CovarianceMatrix.CovarianceMatrixLines,
        )
        for i, field_name in enumerate(_COV_FIELD_ORDER):
            kwargs[field_name] = current_values[i]
        matrices.append(
            OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(
                **kwargs,
            )
        )

    kind: str
    key: str
    value: str
    for kind, key, value in block.get("ordered_items", []):
        if kind == "kv":
            # A new epoch entry signals the start of a new covariance matrix.
            # The epoch keyword name is read from FieldMetadata, not hardcoded.
            if key == _EPOCH_KEYWORD and current_kvs:
                _flush_matrix()
                current_kvs = {}
                current_values = []
            current_kvs[key] = value
        elif kind == "data":
            # Section 5.2.5.4, 5.2.5.5: data line contains whitespace-separated floats.
            current_values.extend(float(token) for token in value.split())

    _flush_matrix()

    return OEM.Segment.CovarianceMatrix(
        comment=comments or None,
        covariance_matrix_lines=matrices,
    )


def _parse_segment(
    meta_block: dict[str, Any],
    data_section: dict[str, Any],
    cov_block: dict[str, Any] | None,
) -> OEM.Segment:
    """
    Build one validated ``OEM.Segment`` from its parsed metadata, ephemeris data, and optional covariance block.

    Args:
        meta_block (dict[str, Any]): Parsed ``META`` block dict.
        data_section (dict[str, Any]): Parsed inter-block data section
            containing raw ephemeris lines.
        cov_block (dict[str, Any] | None): Parsed ``COVARIANCE`` block dict,
            or ``None`` when no covariance data follows this segment.

    Returns:
        OEM.Segment: Fully validated segment containing metadata, ephemeris
        data, and optional covariance matrix.
    """
    # Metadata: keyword map from FieldMetadata annotations (no hardcoding).
    meta_kwargs: dict[str, Any] = map_kvs(
        meta_block["kvs"],
        meta_block["comments"],
        OEM.Segment.Metadata,
    )
    metadata: OEM.Segment.Metadata = OEM.Segment.Metadata(**meta_kwargs)

    # Ephemeris data lines: each is a raw string (section 7.4.1.2).
    ephem_lines: list[OEM.Segment.EphemerisData.EphemerisDataLine] = [
        _parse_ephemeris_line(line)
        for line in data_section.get("data_lines", [])
    ]
    ephem_comments: list[str] = data_section.get("comments", [])
    ephemeris_data: OEM.Segment.EphemerisData = OEM.Segment.EphemerisData(
        comment=ephem_comments or None,
        ephemeris_data_lines=ephem_lines,
    )

    # Optional covariance block.
    cov: OEM.Segment.CovarianceMatrix | None = _parse_covariance_block(cov_block) if cov_block is not None else None

    return OEM.Segment(
        metadata=metadata,
        ephemeris_data=ephemeris_data,
        covariance_matrix=cov,
    )


class KVNOEMReader:
    """
    Read a KVN-format OEM file and return a validated OEM domain model.

    Satisfies ``MessageReaderPort`` structurally.  ``pydantic.ValidationError`` is
    never swallowed: let it propagate to the caller.
    """

    def _parse(
        self,
        text: str,
    ) -> OEM:
        """
        Parse a KVN-format OEM file and return a validated OEM domain model.

        Args:
            text (str): The KVN-format OEM file content.

        Returns:
            OEM: Fully validated OEM domain model.
        """
        raw: dict[str, Any] = parse_kvn(text)
        sections: list[dict[str, Any]] = split_blocks(raw)

        # Derive block delimiter names from the model's Delineation attributes.
        # No string literals like "META_START" appear in this adapter.
        meta_delimiter: str = block_delimiter_name(OEM.Segment.Metadata)          # "META"
        cov_delimiter: str = block_delimiter_name(OEM.Segment.CovarianceMatrix)   # "COVARIANCE"

        # Header
        header_sec: dict[str, Any] = sections[0]
        header_kwargs: dict[str, Any] = map_kvs(
            header_sec["kvs"],
            header_sec["comments"],
            OEM.Header,
        )
        header: OEM.Header = OEM.Header(**header_kwargs)

        # Group remaining sections into segments.
        # OEM KVN structure (section 5.2): one or more repetitions of
        #   META block -> ephemeris data section -> optional COVARIANCE block
        body: list[dict[str, Any]] = sections[1:]
        segments: list[OEM.Segment] = []
        i: int = 0
        while i < len(body):
            section: dict[str, Any] = body[i]
            if section["type"] != "block" or section["delimiter"] != meta_delimiter:
                i += 1
                continue

            meta_block: dict[str, Any] = section
            i += 1

            # Ephemeris data section immediately follows META.
            data_section: dict[str, Any] = {"data_lines": [], "comments": [], "kvs": {}}
            if i < len(body) and body[i]["type"] == "data":
                data_section = body[i]
                i += 1

            # Optional COVARIANCE block.
            cov_block: dict[str, Any] | None = None
            if (
                i < len(body)
                and body[i]["type"] == "block"
                and body[i]["delimiter"] == cov_delimiter
            ):
                cov_block = body[i]
                i += 1

            segments.append(
                _parse_segment(
                    meta_block,
                    data_section,
                    cov_block,
                ),
            )

        return OEM(
            header=header,
            segments=segments,
        )

    def read(
        self,
        path: Path,
    ) -> OEM:
        """
        Read a KVN OEM file and return a validated ``OEM`` domain model.

        Args:
            path (Path): Path to the KVN OEM file.

        Returns:
            OEM: Fully validated OEM domain model.
        """
        return self._parse(path.read_text())

    def read_string(self, content: str) -> OEM:
        """
        Read an OEM KVN string and return a validated OEM domain model.

        Args:
            content (str): The OEM KVN string content.

        Returns:
            OEM: Fully validated OEM domain model.
        """
        return self._parse(content)


OrbitEphemerisMessageKVNReader = KVNOEMReader
