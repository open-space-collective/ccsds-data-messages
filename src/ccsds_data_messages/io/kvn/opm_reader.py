"""
KVN adapter: Orbit Parameter Message reader.

OPM KVN is completely flat: no *_START/*_STOP block delimiters of any kind
(spec Annex G, figures G-1 through G-4). All header, metadata, and data keywords
appear as a single continuous sequence of KEY = VALUE pairs.

Comment attribution follows section 7.8.7: pending comments are flushed to the
logical block of the first keyword that follows them.

Spec references: sections 3.2, 7.3-7.4, 7.8.7, Annex G.
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
from ccsds_data_messages.models.opm import OPM

if TYPE_CHECKING:
    from pathlib import Path

_HEADER_FIELD_MAP = build_keyword_map(OPM.Header)
_META_FIELD_MAP = build_keyword_map(OPM.Metadata)
_STATE_VECTOR_FIELD_MAP = build_keyword_map(OPM.Data.StateVector)
_KEPLERIAN_FIELD_MAP = build_keyword_map(OPM.Data.OsculatingKeplerianElements)
_SPACECRAFT_FIELD_MAP = build_keyword_map(OPM.Data.SpacecraftParameters)
_COVARIANCE_FIELD_MAP = build_keyword_map(OPM.Data.CovarianceMatrix)
_MANEUVER_FIELD_MAP = build_keyword_map(OPM.Data.ManeuverParameters)

# MAN_EPOCH_IGNITION starts each new maneuver group (section 3.2.4.8).
_MAN_EPOCH_KW: str = "MAN_EPOCH_IGNITION"


class KVNOPMReader:
    """
    Reads a KVN-format OPM and returns a validated OPM domain model.

    Satisfies MessageReaderPort structurally. ValidationError is never swallowed.
    """

    def _parse(self, text: str) -> OPM:
        lines = parse_kvn(text, max_line_length=ODM_MAX_LINE_LENGTH)

        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []
        metadata_kvs: dict[str, str] = {}
        metadata_comments: list[str] = []
        state_vector_kvs: dict[str, str] = {}
        state_vector_comments: list[str] = []
        keplerian_kvs: dict[str, str] = {}
        keplerian_comments: list[str] = []
        spacecraft_kvs: dict[str, str] = {}
        spacecraft_comments: list[str] = []
        covariance_kvs: dict[str, str] = {}
        covariance_comments: list[str] = []
        user_kvs: dict[str, str] = {}

        keyword_routing: dict[str, tuple[dict[str, str], list[str]]] = {
            **dict.fromkeys(_HEADER_FIELD_MAP, (header_kvs, header_comments)),
            **dict.fromkeys(_META_FIELD_MAP, (metadata_kvs, metadata_comments)),
            **dict.fromkeys(
                _STATE_VECTOR_FIELD_MAP, (state_vector_kvs, state_vector_comments)
            ),
            **dict.fromkeys(_KEPLERIAN_FIELD_MAP, (keplerian_kvs, keplerian_comments)),
            **dict.fromkeys(_SPACECRAFT_FIELD_MAP, (spacecraft_kvs, spacecraft_comments)),
            **dict.fromkeys(_COVARIANCE_FIELD_MAP, (covariance_kvs, covariance_comments)),
        }

        pending_comments: list[str] = []
        maneuver_groups: list[tuple[dict[str, str], list[str]]] = []
        current_maneuver_kvs: dict[str, str] | None = None
        current_maneuver_comments: list[str] = []

        for line in lines:
            if isinstance(line, BlankLine):
                continue

            if isinstance(line, CommentLine):
                pending_comments.append(line.text)
                continue

            if not isinstance(line, KeyValueLine):
                continue

            if line.keyword == _MAN_EPOCH_KW:
                if current_maneuver_kvs is not None:
                    maneuver_groups.append(
                        (current_maneuver_kvs, current_maneuver_comments)
                    )
                current_maneuver_kvs = {line.keyword: line.value}
                current_maneuver_comments = list(pending_comments)
                pending_comments.clear()
                continue

            if current_maneuver_kvs is not None and line.keyword in _MANEUVER_FIELD_MAP:
                current_maneuver_comments.extend(pending_comments)
                pending_comments.clear()
                current_maneuver_kvs[line.keyword] = line.value
                continue

            if line.keyword.startswith("USER_DEFINED_"):
                # §7.8.7: a COMMENT at the start of the User-Defined Parameters
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

        if current_maneuver_kvs:
            maneuver_groups.append((current_maneuver_kvs, current_maneuver_comments))

        header = OPM.Header(**_to_kwargs(header_kvs, _HEADER_FIELD_MAP, header_comments))
        metadata = OPM.Metadata(
            **_to_kwargs(metadata_kvs, _META_FIELD_MAP, metadata_comments)
        )
        state_vector = OPM.Data.StateVector(
            **_to_kwargs(state_vector_kvs, _STATE_VECTOR_FIELD_MAP, state_vector_comments)
        )
        keplerian = (
            OPM.Data.OsculatingKeplerianElements(
                **_to_kwargs(keplerian_kvs, _KEPLERIAN_FIELD_MAP, keplerian_comments)
            )
            if keplerian_kvs
            else None
        )
        spacecraft = (
            OPM.Data.SpacecraftParameters(
                **_to_kwargs(spacecraft_kvs, _SPACECRAFT_FIELD_MAP, spacecraft_comments)
            )
            if spacecraft_kvs
            else None
        )
        covariance = (
            OPM.Data.CovarianceMatrix(
                **_to_kwargs(covariance_kvs, _COVARIANCE_FIELD_MAP, covariance_comments)
            )
            if covariance_kvs
            else None
        )
        maneuvers = [
            OPM.Data.ManeuverParameters(
                **_to_kwargs(man_kvs, _MANEUVER_FIELD_MAP, man_comments)
            )
            for man_kvs, man_comments in maneuver_groups
        ] or None
        user_defined = (
            OPM.Data.UserDefinedParameters(user_defined=user_kvs) if user_kvs else None
        )

        data = OPM.Data(
            state_vector=state_vector,
            osculating_keplerian_elements=keplerian,
            spacecraft_parameters=spacecraft,
            covariance_matrix=covariance,
            maneuvers=maneuvers,
            user_defined=user_defined,
        )

        return OPM(header=header, metadata=metadata, data=data)

    def read(self, path: Path) -> OPM:
        return self._parse(path.read_text(encoding="utf-8"))

    def read_string(self, content: str) -> OPM:
        return self._parse(content)


OrbitParameterMessageKVNReader = KVNOPMReader
