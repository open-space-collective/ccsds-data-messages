"""
KVN adapter: Orbit Parameter Message reader.

OPM KVN is completely flat: no ``*_START``/``*_STOP`` block delimiters of any kind
(spec Annex G, figures G-1 through G-4).  All header, metadata, and data
keywords appear as a single continuous sequence of ``KEY = VALUE`` pairs.

Comment attribution follows section 7.8.7: ``"Comments in the OPM may appear in the OPM Header immediately after the 'CCSDS_OPM_VERS' keyword, at the very beginning of the OPM Metadata section, and at the beginning of a logical block in the OPM Data section."``

Implementation rule: pending comments are flushed to the logical block of the first keyword that follows them.

Spec references:
- Section 3.2 (OPM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.8.7 (comments)
- Annex G (examples)
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
_HEADER_MAP: dict[str, str] = build_keyword_map(OPM.Header)
_META_MAP: dict[str, str] = build_keyword_map(OPM.Metadata)
_SV_MAP: dict[str, str] = build_keyword_map(OPM.Data.StateVector)
_KE_MAP: dict[str, str] = build_keyword_map(OPM.Data.OsculatingKeplerianElements)
_SP_MAP: dict[str, str] = build_keyword_map(OPM.Data.SpacecraftParameters)
_COV_MAP: dict[str, str] = build_keyword_map(OPM.Data.CovarianceMatrix)
_MAN_MAP: dict[str, str] = build_keyword_map(OPM.Data.ManeuverParameters)

# The keyword that signals the start of a new maneuver set (first keyword
# in table 3-3 per section 3.2.4.8). Discovered via ``block_start=True`` on the model field declaration.
_MAN_EPOCH_KW: str = block_start_keyword(OPM.Data.ManeuverParameters)


class KVNOPMReader:
    """
    Reads a KVN-format OPM file and returns a validated OPM domain model.

    Satisfies ``MessageReaderPort`` structurally.  ``pydantic.ValidationError`` is
    never swallowed: let it propagate to the caller.
    """

    def _parse(
        self,
        text: str,
    ) -> OPM:
        """
        Parse a KVN-format OPM file and return a validated OPM domain model.

        Args:
            text (str): The KVN-format OPM file content.
        
        Returns:
            OPM: Fully validated OPM domain model.
        """
        raw: dict[str, Any] = parse_kvn(text)
        ordered: list[tuple[str, str | None, str | None]] = raw.get("header_ordered_items", [])

        # Accumulators: one ``(kvs, comments)`` pair per logical block.
        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []
        metadata_kvs: dict[str, str] = {}
        metadata_comments: list[str] = []
        state_vector_kvs: dict[str, str] = {}
        state_vector_comments: list[str] = []
        osculating_keplerian_elements_kvs: dict[str, str] = {}
        osculating_keplerian_elements_comments: list[str] = []
        spacecraft_parameters_kvs: dict[str, str] = {}
        spacecraft_parameters_comments: list[str] = []
        covariance_matrix_kvs: dict[str, str] = {}
        covariance_matrix_comments: list[str] = []
        user_kvs: dict[str, str] = {}

        block_maps: list[tuple[dict[str, str], dict[str, str], list[str]]] = [
            (_HEADER_MAP, header_kvs,header_comments),
            (_META_MAP, metadata_kvs, metadata_comments),
            (_SV_MAP, state_vector_kvs, state_vector_comments),
            (_KE_MAP, osculating_keplerian_elements_kvs, osculating_keplerian_elements_comments),
            (_SP_MAP, spacecraft_parameters_kvs, spacecraft_parameters_comments),
            (_COV_MAP, covariance_matrix_kvs, covariance_matrix_comments),
        ]

        maneuver_groups: list[tuple[dict[str, str], list[str]]] = dispatch_flat_kvs(
            ordered,
            block_maps,
            user_kvs=user_kvs,
            maneuver_key=_MAN_EPOCH_KW,
            maneuver_map=_MAN_MAP,
        )

        header: OPM.Header = OPM.Header(
            **map_kvs(
                header_kvs,
                header_comments,
                OPM.Header,
            )
        )
        metadata: OPM.Metadata = OPM.Metadata(
            **map_kvs(
                metadata_kvs,
                metadata_comments,
                OPM.Metadata,
            )
        )

        state_vector: OPM.Data.StateVector = OPM.Data.StateVector(
            **map_kvs(
                state_vector_kvs,
                state_vector_comments,
                OPM.Data.StateVector,
            )
        )
        keplerian: OPM.Data.OsculatingKeplerianElements | None = (
            OPM.Data.OsculatingKeplerianElements(
                **map_kvs(
                    osculating_keplerian_elements_kvs,
                    osculating_keplerian_elements_comments,
                    OPM.Data.OsculatingKeplerianElements,
                )
            )
            if osculating_keplerian_elements_kvs
            else None
        )
        spacecraft: OPM.Data.SpacecraftParameters | None = (
            OPM.Data.SpacecraftParameters(
                **map_kvs(spacecraft_parameters_kvs, spacecraft_parameters_comments,
                          OPM.Data.SpacecraftParameters)
            )
            if spacecraft_parameters_kvs
            else None
        )
        cov: OPM.Data.CovarianceMatrix | None = (
            OPM.Data.CovarianceMatrix(
                **map_kvs(covariance_matrix_kvs, covariance_matrix_comments,
                          OPM.Data.CovarianceMatrix)
            )
            if covariance_matrix_kvs
            else None
        )
        maneuvers: list[OPM.Data.ManeuverParameters] | None = (
            [
                OPM.Data.ManeuverParameters(
                    **map_kvs(
                        maneuver_kvs,
                        comments,
                        OPM.Data.ManeuverParameters,
                    )
                )
                for maneuver_kvs, comments in maneuver_groups
            ]
            or None
        )
        user: OPM.Data.UserDefinedParameters | None = (
            OPM.Data.UserDefinedParameters(
                **map_kvs(
                    user_kvs,
                    [],
                    OPM.Data.UserDefinedParameters,
                )
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

        return OPM(
            header=header,
            metadata=metadata,
            data=data,
        )

    def read(
        self,
        path: Path,
    ) -> OPM:
        """
        Read a KVN OPM file and return a validated ``OPM`` domain model.

        Args:
            path (Path): The path to the KVN OPM file.

        Returns:
            OPM: Fully validated ``OPM`` domain model.
        """
        return self._parse(path.read_text())

    def read_string(
        self,
        content: str,
    ) -> OPM:
        """
        Read an OPM KVN string and return a validated ``OPM`` domain model.

        Args:
            content (str): The KVN-format OPM file content.

        Returns:
            OPM: Fully validated ``OPM`` domain model.
        """
        return self._parse(content)


OrbitParameterMessageKVNReader = KVNOPMReader
