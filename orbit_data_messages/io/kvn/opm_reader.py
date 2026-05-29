"""
KVN adapter: Orbit Parameter Message reader.

OPM KVN is completely flat — no *_START/*_STOP block delimiters of any kind
(spec Annex G, figures G-1 through G-4).  All header, metadata, and data
keywords appear as a single continuous sequence of KEY = VALUE pairs.

Comment attribution follows §7.8.7:
  "Comments in the OPM may appear in the OPM Header immediately after the
   'CCSDS_OPM_VERS' keyword, at the very beginning of the OPM Metadata
   section, and at the beginning of a logical block in the OPM Data section."

Implementation rule: pending comments are flushed to the logical block of
the first keyword that follows them.

Spec references: §3.2 (OPM structure), §7.3–7.4 (KVN rules),
                 §7.8.7 (comment placement), Annex G (examples).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import build_keyword_map
from orbit_data_messages.io.kvn._utils import field_keyword
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.models.opm import OPM

# Keyword maps — built from FieldMetadata annotations, not hardcoded.
_HEADER_MAP = build_keyword_map(OPM.Header)
_META_MAP   = build_keyword_map(OPM.Metadata)
_SV_MAP     = build_keyword_map(OPM.Data.StateVector)
_KE_MAP     = build_keyword_map(OPM.Data.OsculatingKeplerianElements)
_SP_MAP     = build_keyword_map(OPM.Data.SpacecraftParameters)
_COV_MAP    = build_keyword_map(OPM.Data.CovarianceMatrix)
_MAN_MAP    = build_keyword_map(OPM.Data.ManeuverParameters)

# The keyword that signals the start of a new maneuver set (first keyword
# in table 3-3 per §3.2.4.8).  Obtained from FieldMetadata, not hardcoded.
_MAN_EPOCH_KW = field_keyword(OPM.Data.ManeuverParameters, "man_epoch_ignition")


def _dispatch_flat(ordered_items: list) -> dict:
    """
    Distribute flat KV pairs and comments across OPM sub-models.

    Comments are attributed to the logical block of the first keyword that
    follows them (§7.8.7).  Multiple maneuver sets (§3.2.4.8) are each
    collected into a separate (kvs, comments) tuple in man_groups.
    """
    pending: list[str] = []  # comments awaiting block assignment

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
    # Each entry is (kvs, comments) for one maneuver set.
    man_groups: list[tuple[dict[str, str], list[str]]] = []
    current_man_kvs: dict[str, str] | None = None
    current_man_comments: list[str] = []
    user_kvs: dict[str, str] = {}

    for kind, key, value in ordered_items:
        if kind == "comment":
            pending.append(value)
            continue
        if kind != "kv":
            continue

        if key == _MAN_EPOCH_KW:
            # §3.2.4.8 — new maneuver set; seal the previous one.
            if current_man_kvs is not None:
                man_groups.append((current_man_kvs, current_man_comments))
            current_man_kvs = {}
            current_man_comments = list(pending)
            pending.clear()
            current_man_kvs[key] = value

        elif current_man_kvs is not None and key in _MAN_MAP:
            # Continuation of the current maneuver set.
            current_man_kvs[key] = value

        elif key in _HEADER_MAP:
            header_comments.extend(pending); pending.clear()
            header_kvs[key] = value

        elif key in _META_MAP:
            meta_comments.extend(pending); pending.clear()
            meta_kvs[key] = value

        elif key in _SV_MAP:
            sv_comments.extend(pending); pending.clear()
            sv_kvs[key] = value

        elif key in _KE_MAP:
            ke_comments.extend(pending); pending.clear()
            ke_kvs[key] = value

        elif key in _SP_MAP:
            sp_comments.extend(pending); pending.clear()
            sp_kvs[key] = value

        elif key in _COV_MAP:
            cov_comments.extend(pending); pending.clear()
            cov_kvs[key] = value

        elif key.startswith("USER_DEFINED_"):
            pending.clear()  # §3.2.4.12 — no comment field on UserDefinedParameters
            user_kvs[key] = value

    # Seal the last maneuver.
    if current_man_kvs:
        man_groups.append((current_man_kvs, current_man_comments))

    return {
        "header_kvs": header_kvs,
        "header_comments": header_comments,
        "meta_kvs": meta_kvs,
        "meta_comments": meta_comments,
        "sv_kvs": sv_kvs,
        "sv_comments": sv_comments,
        "ke_kvs": ke_kvs,
        "ke_comments": ke_comments,
        "sp_kvs": sp_kvs,
        "sp_comments": sp_comments,
        "cov_kvs": cov_kvs,
        "cov_comments": cov_comments,
        "man_groups": man_groups,
        "user_kvs": user_kvs,
    }


class KVNOPMReader:
    """
    Reads a KVN-format OPM file and returns a validated OPM domain model.

    Satisfies MessageReaderPort structurally.  Pydantic ValidationError is
    never swallowed — let it propagate to the caller.
    """

    def read(self, path: Path) -> OPM:
        """Reads a KVN OPM file and returns a validated OPM domain model.

        Args:
            path: Path to the KVN OPM file.

        Returns:
            A fully validated OPM domain model. Pydantic ValidationError is
            never swallowed — it propagates to the caller unchanged.
        """
        text = path.read_text()
        raw = parse_kvn(text)
        ordered = raw.get("header_ordered_items", [])

        parsed = _dispatch_flat(ordered)

        header = OPM.Header(
            **map_kvs(parsed["header_kvs"], parsed["header_comments"], OPM.Header)
        )
        metadata = OPM.Metadata(
            **map_kvs(parsed["meta_kvs"], parsed["meta_comments"], OPM.Metadata)
        )

        state_vector = OPM.Data.StateVector(
            **map_kvs(parsed["sv_kvs"], parsed["sv_comments"], OPM.Data.StateVector)
        )
        keplerian = (
            OPM.Data.OsculatingKeplerianElements(
                **map_kvs(parsed["ke_kvs"], parsed["ke_comments"],
                          OPM.Data.OsculatingKeplerianElements)
            )
            if parsed["ke_kvs"]
            else None
        )
        spacecraft = (
            OPM.Data.SpacecraftParameters(
                **map_kvs(parsed["sp_kvs"], parsed["sp_comments"],
                          OPM.Data.SpacecraftParameters)
            )
            if parsed["sp_kvs"]
            else None
        )
        cov = (
            OPM.Data.CovarianceMatrix(
                **map_kvs(parsed["cov_kvs"], parsed["cov_comments"],
                          OPM.Data.CovarianceMatrix)
            )
            if parsed["cov_kvs"]
            else None
        )
        maneuvers = (
            [
                OPM.Data.ManeuverParameters(
                    **map_kvs(kvs, comments, OPM.Data.ManeuverParameters)
                )
                for kvs, comments in parsed["man_groups"]
            ]
            or None
        )
        user = (
            OPM.Data.UserDefinedParameters(
                **map_kvs(parsed["user_kvs"], [], OPM.Data.UserDefinedParameters)
            )
            if parsed["user_kvs"]
            else None
        )

        data = OPM.Data(
            state_vector=state_vector,
            osculating_keplerian_elements=keplerian,
            spacecraft_parameters=spacecraft,
            covariance_matrix=cov,
            maneuvers=maneuvers,
            user_defined=user,
        )

        return OPM(header=header, metadata=metadata, data=data)


OrbitParameterMessageKVNReader = KVNOPMReader
