"""
KVN adapter: Orbit Parameter Message reader.

OPM KVN is completely flat: no ``*_START``/``*_STOP`` block delimiters of any kind
(spec Annex G, figures G-1 through G-4).  All header, metadata, and data
keywords appear as a single continuous sequence of KEY = VALUE pairs.

Comment attribution follows section 7.8.7: ``"Comments in the OPM may appear in the OPM Header immediately after the 'CCSDS_OPM_VERS' keyword, at the very beginning of the OPM Metadata section, and at the beginning of a logical block in the OPM Data section."``

Implementation rule: pending comments are flushed to the logical block of the first keyword that follows them.

Spec references: section 3.2 (OPM structure), section 7.3-7.4 (KVN rules), section 7.8.7 (comment placement), Annex G (examples).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from orbit_data_messages.io.kvn._utils import block_start_keyword
from orbit_data_messages.io.kvn._utils import build_keyword_map
from orbit_data_messages.io.kvn._utils import dispatch_flat_kvs
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.models.opm import OPM

# Keyword maps: built from FieldMetadata annotations, not hardcoded.
_HEADER_MAP = build_keyword_map(OPM.Header)
_META_MAP   = build_keyword_map(OPM.Metadata)
_SV_MAP     = build_keyword_map(OPM.Data.StateVector)
_KE_MAP     = build_keyword_map(OPM.Data.OsculatingKeplerianElements)
_SP_MAP     = build_keyword_map(OPM.Data.SpacecraftParameters)
_COV_MAP    = build_keyword_map(OPM.Data.CovarianceMatrix)
_MAN_MAP    = build_keyword_map(OPM.Data.ManeuverParameters)

# The keyword that signals the start of a new maneuver set (first keyword
# in table 3-3 per section 3.2.4.8). Discovered via ``block_start=True`` on the model field declaration.
_MAN_EPOCH_KW = block_start_keyword(OPM.Data.ManeuverParameters)


class KVNOPMReader:
    """
    Reads a KVN-format OPM file and returns a validated OPM domain model.

    Satisfies ``MessageReaderPort`` structurally.  ``pydantic.ValidationError`` is
    never swallowed: let it propagate to the caller.
    """

    def read(self, path: Path) -> OPM:
        """
        Read a KVN OPM file and return a validated ``OPM`` domain model.

        Args:
            path (Path): Path to the KVN OPM file.

        Returns:
            OPM: Fully validated OPM domain model.

        Raises:
            pydantic.ValidationError: If the parsed content fails domain model
                validation.
        """
        text: str = path.read_text()
        raw: dict[str, Any] = parse_kvn(text)
        ordered: list[tuple[str, str | None, str | None]] = raw.get("header_ordered_items", [])

        # Accumulators: one ``(kvs, comments)`` pair per logical block.
        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []
        meta_kvs: dict[str, str] = {}
        meta_comments: list[str] = []
        sv_kvs: dict[str, str] = {}
        sv_comments: list[str] = []
        ke_kvs: dict[str, str] = {}
        ke_comments: list[str] = []
        sp_kvs: dict[str, str] = {}
        sp_comments: list[str] = []
        cov_kvs: dict[str, str] = {}
        cov_comments: list[str] = []
        user_kvs: dict[str, str] = {}

        block_maps: list[tuple[dict[str, str], dict[str, str], list[str]]] = [
            (_HEADER_MAP, header_kvs, header_comments),
            (_META_MAP,   meta_kvs,   meta_comments),
            (_SV_MAP,     sv_kvs,     sv_comments),
            (_KE_MAP,     ke_kvs,     ke_comments),
            (_SP_MAP,     sp_kvs,     sp_comments),
            (_COV_MAP,    cov_kvs,    cov_comments),
        ]

        man_groups: list[tuple[dict[str, str], list[str]]] = dispatch_flat_kvs(
            ordered,
            block_maps,
            user_kvs=user_kvs,
            maneuver_key=_MAN_EPOCH_KW,
            maneuver_map=_MAN_MAP,
        )

        header: OPM.Header = OPM.Header(
            **map_kvs(header_kvs, header_comments, OPM.Header)
        )
        metadata: OPM.Metadata = OPM.Metadata(
            **map_kvs(meta_kvs, meta_comments, OPM.Metadata)
        )

        state_vector: OPM.Data.StateVector = OPM.Data.StateVector(
            **map_kvs(sv_kvs, sv_comments, OPM.Data.StateVector)
        )
        keplerian: OPM.Data.OsculatingKeplerianElements | None = (
            OPM.Data.OsculatingKeplerianElements(
                **map_kvs(ke_kvs, ke_comments,
                          OPM.Data.OsculatingKeplerianElements)
            )
            if ke_kvs
            else None
        )
        spacecraft: OPM.Data.SpacecraftParameters | None = (
            OPM.Data.SpacecraftParameters(
                **map_kvs(sp_kvs, sp_comments,
                          OPM.Data.SpacecraftParameters)
            )
            if sp_kvs
            else None
        )
        cov: OPM.Data.CovarianceMatrix | None = (
            OPM.Data.CovarianceMatrix(
                **map_kvs(cov_kvs, cov_comments,
                          OPM.Data.CovarianceMatrix)
            )
            if cov_kvs
            else None
        )
        maneuvers: list[OPM.Data.ManeuverParameters] | None = (
            [
                OPM.Data.ManeuverParameters(
                    **map_kvs(kvs, comments, OPM.Data.ManeuverParameters)
                )
                for kvs, comments in man_groups
            ]
            or None
        )
        user: OPM.Data.UserDefinedParameters | None = (
            OPM.Data.UserDefinedParameters(
                **map_kvs(user_kvs, [], OPM.Data.UserDefinedParameters)
            )
            if user_kvs
            else None
        )

        data: OPM.Data = OPM.Data(
            state_vector=state_vector,
            osculating_keplerian_elements=keplerian,
            spacecraft_parameters=spacecraft,
            covariance_matrix=cov,
            maneuvers=maneuvers,
            user_defined=user,
        )

        return OPM(header=header, metadata=metadata, data=data)


OrbitParameterMessageKVNReader = KVNOPMReader
