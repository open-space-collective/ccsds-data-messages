"""
KVN adapter: Orbit Ephemeris Message reader.

Implements MessageReaderPort for the KVN format.  All keyword strings are read
from FieldMetadata annotations on the OEM domain model; none are hardcoded
here.  Block delimiter names (META, COVARIANCE) are derived from the
Delineation private attributes on the relevant nested classes.

Spec references: §5.2 (OEM structure), §7.3–7.4 (KVN rules),
                 §7.5.10 (date/time format), §7.7.2 (units).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import block_delimiter_name
from orbit_data_messages.io.kvn._utils import build_keyword_map
from orbit_data_messages.io.kvn._utils import field_keyword
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.io.kvn.parser import split_blocks
from orbit_data_messages.models.oem import OEM


# ---------------------------------------------------------------------------
# Covariance field order and epoch keyword — derived from the domain model,
# not hardcoded.
#
# §5.2.5.4 defines the LTM order; the model fields are declared in that same
# order so we can read it from model_fields.  We skip 'epoch' and
# 'cov_ref_frame' (the two header KV fields) to get only the 21 matrix fields.
# ---------------------------------------------------------------------------
_CML = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_CML_KW_MAP = build_keyword_map(_CML)
# Python field names in LTM order (preserves Pydantic field declaration order).
_COV_FIELD_ORDER = [
    fn for fn in _CML.model_fields
    if fn not in ("epoch", "cov_ref_frame")
]
# The KVN keyword for the epoch field — obtained via field_keyword() which reads
# the FieldMetadata annotation on CovarianceMatrixLines.epoch.  This is the only
# sanctioned way to obtain a keyword from a field name in an adapter.
_EPOCH_KEYWORD = field_keyword(_CML, "epoch")


def _parse_ephemeris_line(line: str) -> OEM.Segment.EphemerisData.EphemerisDataLine:
    """
    §5.2.4.1 — each data line begins with an epoch followed by position,
    velocity, and optionally acceleration components.

    7 tokens  → epoch + x y z + x_dot y_dot z_dot
    10 tokens → epoch + x y z + x_dot y_dot z_dot + x_ddot y_ddot z_ddot
    Accelerations are all-or-nothing (§5.2.4.2).
    """
    tokens = line.split()
    if len(tokens) == 7:
        epoch, x, y, z, xd, yd, zd = tokens
        return OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epoch,
            x=float(x), y=float(y), z=float(z),
            x_dot=float(xd), y_dot=float(yd), z_dot=float(zd),
        )
    if len(tokens) == 10:
        epoch, x, y, z, xd, yd, zd, xdd, ydd, zdd = tokens
        return OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epoch,
            x=float(x), y=float(y), z=float(z),
            x_dot=float(xd), y_dot=float(yd), z_dot=float(zd),
            x_ddot=float(xdd), y_ddot=float(ydd), z_ddot=float(zdd),
        )
    raise ValueError(
        f"§5.2.4.1: OEM ephemeris line must have 7 or 10 tokens, "
        f"got {len(tokens)}: {line!r}"
    )


def _parse_covariance_block(
    block: dict,
) -> OEM.Segment.CovarianceMatrix:
    """
    Parse a COVARIANCE block into OEM.Segment.CovarianceMatrix.

    The block may contain one or more covariance matrices, each introduced
    by an EPOCH KV pair and followed by data lines containing the LTM rows
    (§5.2.5.4).  ordered_items is used instead of the flat kvs dict so that
    repeated EPOCH keys are handled correctly.
    """
    cov_kw_map = build_keyword_map(OEM.Segment.CovarianceMatrix)
    line_kw_map = build_keyword_map(OEM.Segment.CovarianceMatrix.CovarianceMatrixLines)

    comments = block.get("comments", [])

    # Walk ordered_items to group [kv* data*]+ into individual matrices.
    matrices: list[OEM.Segment.CovarianceMatrix.CovarianceMatrixLines] = []
    current_kvs: dict[str, str] = {}
    current_values: list[float] = []

    def _flush_matrix() -> None:
        if not current_kvs and not current_values:
            return
        if len(current_values) != 21:
            raise ValueError(
                f"§5.2.5.4: OEM covariance matrix requires exactly 21 LTM "
                f"elements, got {len(current_values)}."
            )
        kwargs = map_kvs(current_kvs, [], OEM.Segment.CovarianceMatrix.CovarianceMatrixLines)
        for i, field_name in enumerate(_COV_FIELD_ORDER):
            kwargs[field_name] = current_values[i]
        matrices.append(
            OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(**kwargs)
        )

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
            # §5.2.5.4 — data line contains whitespace-separated floats.
            current_values.extend(float(tok) for tok in value.split())

    _flush_matrix()

    return OEM.Segment.CovarianceMatrix(
        comment=comments or None,
        covariance_matrix_lines=matrices,
    )


def _parse_segment(
    meta_block: dict,
    data_section: dict,
    cov_block: dict | None,
    *,
    meta_delimiter: str,
) -> OEM.Segment:
    """Build one OEM.Segment from its constituent parsed sections."""
    # Metadata — keyword map from FieldMetadata annotations (no hardcoding).
    meta_kwargs = map_kvs(
        meta_block["kvs"], meta_block["comments"], OEM.Segment.Metadata
    )
    metadata = OEM.Segment.Metadata(**meta_kwargs)

    # Ephemeris data lines — each is a raw string (§7.4.1.2).
    ephem_lines = [
        _parse_ephemeris_line(line)
        for line in data_section.get("data_lines", [])
    ]
    ephem_comments = data_section.get("comments", [])
    ephemeris_data = OEM.Segment.EphemerisData(
        comment=ephem_comments or None,
        ephemeris_data_lines=ephem_lines,
    )

    # Optional covariance block.
    cov = _parse_covariance_block(cov_block) if cov_block is not None else None

    return OEM.Segment(
        metadata=metadata,
        ephemeris_data=ephemeris_data,
        covariance_matrix=cov,
    )


class KVNOEMReader:
    """
    Reads a KVN-format OEM file and returns a validated OEM domain model.

    Satisfies MessageReaderPort structurally.  Pydantic ValidationError is
    never swallowed — let it propagate to the caller.
    """

    def read(self, path: Path) -> OEM:
        """Reads a KVN OEM file and returns a validated OEM domain model.

        Args:
            path: Path to the KVN OEM file.

        Returns:
            A fully validated OEM domain model. Pydantic ValidationError is
            never swallowed — it propagates to the caller unchanged.
        """
        text = path.read_text()
        raw = parse_kvn(text)
        sections = split_blocks(raw)

        # Derive block delimiter names from the model's Delineation attrs —
        # no string literals like "META_START" appear in this adapter.
        meta_delimiter = block_delimiter_name(OEM.Segment.Metadata)          # "META"
        cov_delimiter = block_delimiter_name(OEM.Segment.CovarianceMatrix)   # "COVARIANCE"

        # Header
        header_sec = sections[0]
        header_kwargs = map_kvs(
            header_sec["kvs"], header_sec["comments"], OEM.Header
        )
        header = OEM.Header(**header_kwargs)

        # Group remaining sections into segments.
        # OEM KVN structure (§5.2): one or more repetitions of
        #   META block → ephemeris data section → optional COVARIANCE block
        body = sections[1:]
        segments: list[OEM.Segment] = []
        i = 0
        while i < len(body):
            sec = body[i]
            if sec["type"] != "block" or sec["delimiter"] != meta_delimiter:
                i += 1
                continue

            meta_block = sec
            i += 1

            # Ephemeris data section immediately follows META.
            data_sec: dict = {"data_lines": [], "comments": [], "kvs": {}}
            if i < len(body) and body[i]["type"] == "data":
                data_sec = body[i]
                i += 1

            # Optional COVARIANCE block.
            cov_block: dict | None = None
            if (
                i < len(body)
                and body[i]["type"] == "block"
                and body[i]["delimiter"] == cov_delimiter
            ):
                cov_block = body[i]
                i += 1

            segments.append(
                _parse_segment(
                    meta_block, data_sec, cov_block,
                    meta_delimiter=meta_delimiter,
                )
            )

        return OEM(header=header, segments=segments)


OrbitEphemerisMessageKVNReader = KVNOEMReader
