"""
KVN adapter: Orbit Comprehensive Message reader.

All keyword strings are read from FieldMetadata annotations on the OCM domain
model — none are hardcoded in this adapter.  Block delimiter names are derived
from the Delineation private attributes on the relevant nested classes.

Spec references: §6.2 (OCM structure), §7.3–7.4 (KVN rules).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import block_delimiter_name
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.io.kvn.parser import split_blocks
from orbit_data_messages.models.ocm import OCM

# All block delimiter names come from Delineation on the model classes —
# no *_START or *_STOP string literals appear in this adapter.
_META_D = block_delimiter_name(OCM.Metadata)                    # "META"
_TRAJ_D = block_delimiter_name(OCM.TrajectoryStateBlock)        # "TRAJ"
_PHYS_D = block_delimiter_name(OCM.PhysicalPropertiesBlock)     # "PHYS"
_COV_D  = block_delimiter_name(OCM.CovarianceBlock)             # "COV"
_MAN_D  = block_delimiter_name(OCM.ManeuverBlock)               # "MAN"
_PERT_D = block_delimiter_name(OCM.PerturbationsBlock)          # "PERT"
_OD_D   = block_delimiter_name(OCM.OrbitDeterminationBlock)     # "OD"
_USER_D = block_delimiter_name(OCM.UserDefinedParameters)       # "USER"


def _parse_traj_block(block: dict) -> OCM.TrajectoryStateBlock:
    """Parse a TRAJ block; data_lines are raw trajectory state lines (§7.4.1.5)."""
    kwargs = map_kvs(block["kvs"], block["comments"], OCM.TrajectoryStateBlock)
    kwargs["data_lines"] = block.get("data_lines") or []
    return OCM.TrajectoryStateBlock(**kwargs)


def _parse_cov_block(block: dict) -> OCM.CovarianceBlock:
    """Parse a COV block; data_lines are raw covariance lines (§7.4.1.6)."""
    kwargs = map_kvs(block["kvs"], block["comments"], OCM.CovarianceBlock)
    kwargs["data_lines"] = block.get("data_lines") or []
    return OCM.CovarianceBlock(**kwargs)


def _parse_man_block(block: dict) -> OCM.ManeuverBlock:
    """Parse a MAN block; data_lines are raw maneuver lines (§7.4.1.7)."""
    kwargs = map_kvs(block["kvs"], block["comments"], OCM.ManeuverBlock)
    kwargs["data_lines"] = block.get("data_lines") or []
    return OCM.ManeuverBlock(**kwargs)


class KVNOCMReader:
    """
    Reads a KVN-format OCM file and returns a validated OCM domain model.

    Satisfies MessageReaderPort structurally.  Pydantic ValidationError is
    never swallowed — let it propagate to the caller.
    """

    def read(self, path: Path) -> OCM:
        text = path.read_text()
        raw = parse_kvn(text)
        sections = split_blocks(raw)

        # Header
        header_sec = sections[0]
        header = OCM.Header(
            **map_kvs(header_sec["kvs"], header_sec["comments"], OCM.Header)
        )

        # Collect named blocks by their delimiter type.
        meta_block: dict | None = None
        traj_blocks: list[dict] = []
        phys_block: dict | None = None
        cov_blocks: list[dict] = []
        man_blocks: list[dict] = []
        pert_block: dict | None = None
        od_block: dict | None = None
        user_block: dict | None = None

        for sec in sections[1:]:
            if sec["type"] != "block":
                continue
            d = sec["delimiter"]
            if d == _META_D:
                meta_block = sec
            elif d == _TRAJ_D:
                traj_blocks.append(sec)
            elif d == _PHYS_D:
                phys_block = sec
            elif d == _COV_D:
                cov_blocks.append(sec)
            elif d == _MAN_D:
                man_blocks.append(sec)
            elif d == _PERT_D:
                pert_block = sec
            elif d == _OD_D:
                od_block = sec
            elif d == _USER_D:
                user_block = sec

        if meta_block is None:
            raise ValueError("OCM/KVN: required META block not found.")

        metadata = OCM.Metadata(
            **map_kvs(meta_block["kvs"], meta_block["comments"], OCM.Metadata)
        )

        trajectory_states = (
            [_parse_traj_block(b) for b in traj_blocks] or None
        )
        physical_properties = (
            OCM.PhysicalPropertiesBlock(
                **map_kvs(phys_block["kvs"], phys_block["comments"], OCM.PhysicalPropertiesBlock)
            )
            if phys_block is not None
            else None
        )
        covariances = (
            [_parse_cov_block(b) for b in cov_blocks] or None
        )
        maneuvers = (
            [_parse_man_block(b) for b in man_blocks] or None
        )
        perturbations = (
            OCM.PerturbationsBlock(
                **map_kvs(pert_block["kvs"], pert_block["comments"], OCM.PerturbationsBlock)
            )
            if pert_block is not None
            else None
        )
        orbit_determination = (
            OCM.OrbitDeterminationBlock(
                **map_kvs(od_block["kvs"], od_block["comments"], OCM.OrbitDeterminationBlock)
            )
            if od_block is not None
            else None
        )
        user_defined = (
            OCM.UserDefinedParameters(
                **map_kvs(user_block["kvs"], user_block["comments"], OCM.UserDefinedParameters)
            )
            if user_block is not None
            else None
        )

        return OCM(
            header=header,
            metadata=metadata,
            trajectory_states=trajectory_states,
            physical_properties=physical_properties,
            covariances=covariances,
            maneuvers=maneuvers,
            perturbations=perturbations,
            orbit_determination=orbit_determination,
            user_defined=user_defined,
        )


OrbitComprehensiveMessageKVNReader = KVNOCMReader
