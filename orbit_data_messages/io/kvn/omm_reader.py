"""
KVN adapter: Orbit Mean-Elements Message reader.

OMM KVN is completely flat — no *_START/*_STOP block delimiters of any kind
(spec Annex G, figures G-7 and G-8).  All header, metadata, and data keywords
appear as a single continuous sequence of KEY = VALUE pairs.

Comment attribution follows §7.8.8:
  "Comments in the OMM may appear in the OMM Header immediately after the
   'CCSDS_OMM_VERS' keyword, at the very beginning of the OMM Metadata
   section, and at the beginning of a logical block in the OMM Data section."

Implementation rule: pending comments are flushed to the logical block of
the first keyword that follows them.

Spec references: §4.2 (OMM structure), §7.3–7.4 (KVN rules),
                 §7.8.8 (comment placement), Annex G (examples).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import build_keyword_map
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.models.omm import OMM

_HEADER_MAP = build_keyword_map(OMM.Header)
_META_MAP   = build_keyword_map(OMM.Metadata)
_ME_MAP     = build_keyword_map(OMM.Data.MeanKeplerianElements)
_SP_MAP     = build_keyword_map(OMM.Data.SpacecraftParameters)
_TLE_MAP    = build_keyword_map(OMM.Data.TLERelatedParameters)
_COV_MAP    = build_keyword_map(OMM.Data.CovarianceMatrix)


def _dispatch_flat(ordered_items: list) -> dict:
    """
    Distribute flat KV pairs and comments across OMM sub-models.

    Comments are attributed to the logical block of the first keyword that
    follows them (§7.8.8).  OMM has no maneuver section (§4.2.4.8).
    """
    pending: list[str] = []

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

    for kind, key, value in ordered_items:
        if kind == "comment":
            pending.append(value)
            continue
        if kind != "kv":
            continue

        if key in _HEADER_MAP:
            header_comments.extend(pending); pending.clear()
            header_kvs[key] = value

        elif key in _META_MAP:
            meta_comments.extend(pending); pending.clear()
            meta_kvs[key] = value

        elif key in _ME_MAP:
            me_comments.extend(pending); pending.clear()
            me_kvs[key] = value

        elif key in _SP_MAP:
            sp_comments.extend(pending); pending.clear()
            sp_kvs[key] = value

        elif key in _TLE_MAP:
            tle_comments.extend(pending); pending.clear()
            tle_kvs[key] = value

        elif key in _COV_MAP:
            cov_comments.extend(pending); pending.clear()
            cov_kvs[key] = value

        elif key.startswith("USER_DEFINED_"):
            pending.clear()  # no comment field on OMM.Data.UserDefinedParameters
            user_kvs[key] = value

    return {
        "header_kvs": header_kvs,
        "header_comments": header_comments,
        "meta_kvs": meta_kvs,
        "meta_comments": meta_comments,
        "me_kvs": me_kvs,
        "me_comments": me_comments,
        "sp_kvs": sp_kvs,
        "sp_comments": sp_comments,
        "tle_kvs": tle_kvs,
        "tle_comments": tle_comments,
        "cov_kvs": cov_kvs,
        "cov_comments": cov_comments,
        "user_kvs": user_kvs,
    }


class KVNOMMReader:
    """
    Reads a KVN-format OMM file and returns a validated OMM domain model.

    Satisfies MessageReaderPort structurally.  Pydantic ValidationError is
    never swallowed — let it propagate to the caller.
    """

    def read(self, path: Path) -> OMM:
        """Reads a KVN OMM file and returns a validated OMM domain model.

        Args:
            path: Path to the KVN OMM file.

        Returns:
            A fully validated OMM domain model. Pydantic ValidationError is
            never swallowed — it propagates to the caller unchanged.
        """
        text = path.read_text()
        raw = parse_kvn(text)
        ordered = raw.get("header_ordered_items", [])

        parsed = _dispatch_flat(ordered)

        header = OMM.Header(
            **map_kvs(parsed["header_kvs"], parsed["header_comments"], OMM.Header)
        )
        metadata = OMM.Metadata(
            **map_kvs(parsed["meta_kvs"], parsed["meta_comments"], OMM.Metadata)
        )
        mean_keplerian = OMM.Data.MeanKeplerianElements(
            **map_kvs(parsed["me_kvs"], parsed["me_comments"], OMM.Data.MeanKeplerianElements)
        )
        spacecraft = (
            OMM.Data.SpacecraftParameters(
                **map_kvs(parsed["sp_kvs"], parsed["sp_comments"], OMM.Data.SpacecraftParameters)
            )
            if parsed["sp_kvs"]
            else None
        )
        tle_params = (
            OMM.Data.TLERelatedParameters(
                **map_kvs(parsed["tle_kvs"], parsed["tle_comments"], OMM.Data.TLERelatedParameters)
            )
            if parsed["tle_kvs"]
            else None
        )
        cov = (
            OMM.Data.CovarianceMatrix(
                **map_kvs(parsed["cov_kvs"], parsed["cov_comments"], OMM.Data.CovarianceMatrix)
            )
            if parsed["cov_kvs"]
            else None
        )
        user = (
            OMM.Data.UserDefinedParameters(
                **map_kvs(parsed["user_kvs"], [], OMM.Data.UserDefinedParameters)
            )
            if parsed["user_kvs"]
            else None
        )

        data = OMM.Data(
            mean_keplerian_elements=mean_keplerian,
            spacecraft_parameters=spacecraft,
            tle_related_parameters=tle_params,
            covariance_matrix=cov,
            user_defined=user,
        )

        return OMM(header=header, metadata=metadata, data=data)


OrbitMeanElementsMessageKVNReader = KVNOMMReader
