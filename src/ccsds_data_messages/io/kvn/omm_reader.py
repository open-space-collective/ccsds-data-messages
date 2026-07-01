"""
KVN adapter: Orbit Mean Elements Message reader.

OMM KVN is completely flat: no *_START/*_STOP block delimiters of any kind
(spec Annex G, figures G-7 and G-8). All header, metadata, and data keywords
appear as a single continuous sequence of KEY = VALUE pairs.

Maneuvers are not accommodated in the OMM (section 4.2.4.8).

Comment attribution follows section 7.8.8: pending comments are flushed to the
logical block of the first keyword that follows them.

Spec references: sections 4.2, 7.3-7.4, 7.8.8, Annex G.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ccsds_data_messages.io._utils import build_keyword_map
from ccsds_data_messages.io.kvn._utils import to_kwargs as _to_kwargs
from ccsds_data_messages.io.kvn.parser import (
    ODM_MAX_LINE_LENGTH,
    BlankLine,
    CommentLine,
    KeyValueLine,
    parse_kvn,
)
from ccsds_data_messages.models.omm import OMM

if TYPE_CHECKING:
    from pathlib import Path

_HEADER_FIELD_MAP = build_keyword_map(OMM.Header)
_META_FIELD_MAP = build_keyword_map(OMM.Metadata)
_MEAN_KEPLERIAN_FIELD_MAP = build_keyword_map(OMM.Data.MeanKeplerianElements)
_SPACECRAFT_FIELD_MAP = build_keyword_map(OMM.Data.SpacecraftParameters)
_TLE_FIELD_MAP = build_keyword_map(OMM.Data.TLERelatedParameters)
_COVARIANCE_FIELD_MAP = build_keyword_map(OMM.Data.CovarianceMatrix)


class KVNOMMReader:
    """
    Reads a KVN-format OMM and returns a validated OMM domain model.

    Satisfies MessageReaderPort structurally. ValidationError is never swallowed.
    """

    def _parse(self, text: str) -> OMM:
        lines = parse_kvn(text, max_line_length=ODM_MAX_LINE_LENGTH)

        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []
        metadata_kvs: dict[str, str] = {}
        metadata_comments: list[str] = []
        mean_keplerian_kvs: dict[str, str] = {}
        mean_keplerian_comments: list[str] = []
        spacecraft_kvs: dict[str, str] = {}
        spacecraft_comments: list[str] = []
        tle_kvs: dict[str, str] = {}
        tle_comments: list[str] = []
        covariance_kvs: dict[str, str] = {}
        covariance_comments: list[str] = []
        user_kvs: dict[str, str] = {}

        keyword_routing: dict[str, tuple[dict[str, str], list[str]]] = {
            **dict.fromkeys(_HEADER_FIELD_MAP, (header_kvs, header_comments)),
            **dict.fromkeys(_META_FIELD_MAP, (metadata_kvs, metadata_comments)),
            **dict.fromkeys(
                _MEAN_KEPLERIAN_FIELD_MAP, (mean_keplerian_kvs, mean_keplerian_comments)
            ),
            **dict.fromkeys(_SPACECRAFT_FIELD_MAP, (spacecraft_kvs, spacecraft_comments)),
            **dict.fromkeys(_TLE_FIELD_MAP, (tle_kvs, tle_comments)),
            **dict.fromkeys(_COVARIANCE_FIELD_MAP, (covariance_kvs, covariance_comments)),
        }

        pending_comments: list[str] = []

        for line in lines:
            if isinstance(line, BlankLine):
                continue

            if isinstance(line, CommentLine):
                pending_comments.append(line.text)
                continue

            if not isinstance(line, KeyValueLine):
                continue

            if line.keyword.startswith("USER_DEFINED_"):
                # §7.8.8: a COMMENT at the start of the User-Defined Parameters
                # block is valid placement, but UserDefinedParameters has no
                # comment field to attribute it to — known limitation, dropped.
                pending_comments.clear()
                user_kvs[line.keyword[len("USER_DEFINED_") :]] = line.value
                continue

            if line.keyword in keyword_routing:
                target_kvs, target_comments = keyword_routing[line.keyword]
                target_comments.extend(pending_comments)
                pending_comments.clear()
                target_kvs[line.keyword] = line.value

        header = OMM.Header(**_to_kwargs(header_kvs, _HEADER_FIELD_MAP, header_comments))
        metadata = OMM.Metadata(
            **_to_kwargs(metadata_kvs, _META_FIELD_MAP, metadata_comments)
        )
        mean_keplerian = OMM.Data.MeanKeplerianElements(
            **_to_kwargs(
                mean_keplerian_kvs, _MEAN_KEPLERIAN_FIELD_MAP, mean_keplerian_comments
            )
        )
        spacecraft = (
            OMM.Data.SpacecraftParameters(
                **_to_kwargs(spacecraft_kvs, _SPACECRAFT_FIELD_MAP, spacecraft_comments)
            )
            if spacecraft_kvs
            else None
        )
        tle_params = (
            OMM.Data.TLERelatedParameters(
                **_to_kwargs(tle_kvs, _TLE_FIELD_MAP, tle_comments)
            )
            if tle_kvs
            else None
        )
        covariance = (
            OMM.Data.CovarianceMatrix(
                **_to_kwargs(covariance_kvs, _COVARIANCE_FIELD_MAP, covariance_comments)
            )
            if covariance_kvs
            else None
        )
        user_defined = (
            OMM.Data.UserDefinedParameters(user_defined=user_kvs) if user_kvs else None
        )

        data = OMM.Data(
            mean_keplerian_elements=mean_keplerian,
            spacecraft_parameters=spacecraft,
            tle_related_parameters=tle_params,
            covariance_matrix=covariance,
            user_defined=user_defined,
        )

        return OMM(header=header, metadata=metadata, data=data)

    def read(self, path: Path) -> OMM:
        return self._parse(path.read_text(encoding="utf-8"))

    def read_string(self, content: str) -> OMM:
        return self._parse(content)


OrbitMeanElementsMessageKVNReader = KVNOMMReader
