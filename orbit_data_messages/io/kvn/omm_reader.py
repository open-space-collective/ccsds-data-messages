"""
OMM KVN is completely flat: no ``*_START``/``*_STOP`` block delimiters of any kind
(spec Annex G, figures G-7 and G-8).  All header, metadata, and data keywords
appear as a single continuous sequence of ``KEY = VALUE`` pairs.

Comment attribution follows section 7.8.8: ``"Comments in the OMM may appear in the OMM Header immediately after the 'CCSDS_OMM_VERS' keyword, at the very beginning of the OMM Metadata section, and at the beginning of a logical block in the OMM Data section."``

Implementation rule: pending comments are flushed to the logical block of the first keyword that follows them.

Spec references:
- Section 4.2 (OMM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.8.8 (comments)
- Annex G (examples)
"""
from __future__ import annotations

from typing import Any
from pathlib import Path

from orbit_data_messages.io.kvn._utils import build_keyword_map
from orbit_data_messages.io.kvn._utils import dispatch_flat_kvs
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.models.omm import OMM

_HEADER_MAP: dict[str, str] = build_keyword_map(OMM.Header)
_META_MAP: dict[str, str] = build_keyword_map(OMM.Metadata)
_ME_MAP: dict[str, str] = build_keyword_map(OMM.Data.MeanKeplerianElements)
_SP_MAP: dict[str, str] = build_keyword_map(OMM.Data.SpacecraftParameters)
_TLE_MAP: dict[str, str] = build_keyword_map(OMM.Data.TLERelatedParameters)
_COV_MAP: dict[str, str] = build_keyword_map(OMM.Data.CovarianceMatrix)


class KVNOMMReader:
    """
    Read a KVN-format OMM file and return a validated OMM domain model.

    Satisfies ``MessageReaderPort`` structurally.  ``pydantic.ValidationError`` is
    never swallowed: let it propagate to the caller.
    """

    def _parse(self, text: str) -> OMM:
        raw: dict[str, Any] = parse_kvn(text)
        ordered: list[tuple[str, str | None, str | None]] = raw.get("header_ordered_items", [])

        # Accumulators: one (kvs, comments) pair per logical block.
        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []
        meta_kvs: dict[str, str] = {}
        meta_comments: list[str] = []
        me_kvs: dict[str, str] = {}
        me_comments: list[str] = []
        sp_kvs: dict[str, str] = {}
        sp_comments: list[str] = []
        tle_kvs: dict[str, str] = {}
        tle_comments: list[str] = []
        cov_kvs: dict[str, str] = {}
        cov_comments: list[str] = []
        user_kvs: dict[str, str] = {}

        dispatch_flat_kvs(
            ordered,
            [
                (_HEADER_MAP, header_kvs, header_comments),
                (_META_MAP,   meta_kvs,   meta_comments),
                (_ME_MAP,     me_kvs,     me_comments),
                (_SP_MAP,     sp_kvs,     sp_comments),
                (_TLE_MAP,    tle_kvs,    tle_comments),
                (_COV_MAP,    cov_kvs,    cov_comments),
            ],
            user_kvs=user_kvs,
            # OMM has no maneuver section (section 4.2.4.8): no maneuver_key or maneuver_map needed.
        )

        header: OMM.Header = OMM.Header(
            **map_kvs(
                header_kvs,
                header_comments,
                OMM.Header,
            )
        )
        metadata: OMM.Metadata = OMM.Metadata(
            **map_kvs(
                meta_kvs,
                meta_comments,
                OMM.Metadata,
            )
        )
        mean_keplerian: OMM.Data.MeanKeplerianElements = OMM.Data.MeanKeplerianElements(
            **map_kvs(
                me_kvs,
                me_comments,
                OMM.Data.MeanKeplerianElements,
            )
        )
        spacecraft: OMM.Data.SpacecraftParameters | None = (
            OMM.Data.SpacecraftParameters(
                **map_kvs(
                    sp_kvs,
                    sp_comments,
                    OMM.Data.SpacecraftParameters,
                )
            )
            if sp_kvs
            else None
        )
        tle_params: OMM.Data.TLERelatedParameters | None = (
            OMM.Data.TLERelatedParameters(
                **map_kvs(
                    tle_kvs,
                    tle_comments,
                    OMM.Data.TLERelatedParameters,
                )
            )
            if tle_kvs
            else None
        )
        cov: OMM.Data.CovarianceMatrix | None = (
            OMM.Data.CovarianceMatrix(
                **map_kvs(
                    cov_kvs,
                    cov_comments,
                    OMM.Data.CovarianceMatrix,
                )
            )
            if cov_kvs
            else None
        )
        user: OMM.Data.UserDefinedParameters | None = (
            OMM.Data.UserDefinedParameters(
                **map_kvs(
                    user_kvs,
                    [],
                    OMM.Data.UserDefinedParameters,
                )
            )
            if user_kvs
            else None
        )

        data: OMM.Data = OMM.Data(
            mean_keplerian_elements=mean_keplerian,
            spacecraft_parameters=spacecraft,
            tle_related_parameters=tle_params,
            covariance_matrix=cov,
            user_defined=user,
        )

        return OMM(
            header=header,
            metadata=metadata,
            data=data,
        )

    def read(
        self,
        path: Path,
    ) -> OMM:
        """
        Read a KVN OMM file and return a validated OMM domain model.

        Args:
            path (Path): The path to the KVN OMM file.

        Returns:
            OMM: Fully validated OMM domain model.
        """
        return self._parse(path.read_text())

    def read_string(
        self,
        content: str,
    ) -> OMM:
        """
        Read an OMM KVN string and return a validated OMM domain model.

        Args:
            content (str): The KVN-format OMM file content.

        Returns:
            OMM: Fully validated OMM domain model.
        """
        return self._parse(content)


OrbitMeanElementsMessageKVNReader = KVNOMMReader
