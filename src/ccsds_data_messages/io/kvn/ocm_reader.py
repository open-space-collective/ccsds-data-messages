"""
KVN adapter: Orbit Comprehensive Message reader.

OCM KVN is block-structured: the file begins with a header section (flat KV pairs),
followed by named blocks delimited by *_START/*_STOP keywords. Block names are
derived from the Delineation class variables on the OCM model — no strings are
hardcoded here.

Spec references:
- Section 6.2 (OCM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.8.10 (comments)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io._utils import map_kvs
from ccsds_data_messages.io.kvn._utils import required_block_delimiter_name
from ccsds_data_messages.io.kvn.parser import (
    BlankLine,
    BlockStartLine,
    BlockStopLine,
    CommentLine,
    DataLine,
    KeyValueLine,
    parse_kvn,
)
from ccsds_data_messages.models.ocm import OCM

if TYPE_CHECKING:
    from pathlib import Path

_T = TypeVar("_T", bound=BaseModel)

# Block delimiter names — derived from model Delineation class variables; no literals.
_META_D: str = required_block_delimiter_name(OCM.Metadata)  # "META"
_TRAJ_D: str = required_block_delimiter_name(OCM.TrajectoryStateTimeHistory)  # "TRAJ"
_PHYS_D: str = required_block_delimiter_name(
    OCM.SpaceObjectPhysicalCharacteristics
)  # "PHYS"
_COV_D: str = required_block_delimiter_name(OCM.CovarianceTimeHistory)  # "COV"
_MAN_D: str = required_block_delimiter_name(OCM.ManeuverSpecification)  # "MAN"
_PERT_D: str = required_block_delimiter_name(OCM.PerturbationsSpecification)  # "PERT"
_OD_D: str = required_block_delimiter_name(OCM.OrbitDeterminationData)  # "OD"
_USER_D: str = required_block_delimiter_name(OCM.UserDefinedParameters)  # "USER"


def _parse_data_block(
    block: dict[str, Any],
    model_class: type[_T],
) -> _T:
    """
    Build a model instance from a block dict that may include raw data lines.

    ``block`` must have keys ``"kvs"``, ``"comments"``, and ``"data_lines"``.
    ``data_lines`` holds the verbatim whitespace-separated rows that follow the
    KV section within the block (TRAJ, COV, MAN sections per spec 6.2.x).
    """
    kwargs: dict[str, Any] = map_kvs(block["kvs"], block["comments"], model_class)
    kwargs["data_lines"] = block.get("data_lines") or []
    return model_class(**kwargs)


class KVNOCMReader:
    """
    Read a KVN-format OCM file and return a validated OCM domain model.

    Satisfies MessageReaderPort structurally. ValidationError is never swallowed.
    """

    def _parse(self, text: str) -> OCM:
        lines = parse_kvn(text)

        header_kvs: dict[str, str] = {}
        header_comments: list[str] = []

        meta_block: dict[str, Any] | None = None
        traj_blocks: list[dict[str, Any]] = []
        phys_block: dict[str, Any] | None = None
        cov_blocks: list[dict[str, Any]] = []
        man_blocks: list[dict[str, Any]] = []
        pert_block: dict[str, Any] | None = None
        od_block: dict[str, Any] | None = None
        user_block: dict[str, Any] | None = None

        pending: list[str] = []
        current_block: dict[str, Any] | None = None
        in_block: bool = False

        def _seal_block(block_name: str) -> None:
            nonlocal meta_block, phys_block, pert_block, od_block, user_block
            if current_block is None:
                raise ParseError(
                    f"OCM/KVN: '{block_name}_STOP' without a preceding '{block_name}_START'"
                )
            if block_name == _META_D:
                meta_block = current_block
            elif block_name == _TRAJ_D:
                traj_blocks.append(current_block)
            elif block_name == _PHYS_D:
                phys_block = current_block
            elif block_name == _COV_D:
                cov_blocks.append(current_block)
            elif block_name == _MAN_D:
                man_blocks.append(current_block)
            elif block_name == _PERT_D:
                pert_block = current_block
            elif block_name == _OD_D:
                od_block = current_block
            elif block_name == _USER_D:
                user_block = current_block

        for line in lines:
            if isinstance(line, BlankLine):
                continue

            if isinstance(line, CommentLine):
                pending.append(line.text)
                continue

            if isinstance(line, BlockStartLine):
                current_block = {"kvs": {}, "comments": list(pending), "data_lines": []}
                pending.clear()
                in_block = True
                continue

            if isinstance(line, BlockStopLine):
                _seal_block(line.block_name)
                current_block = None
                in_block = False
                continue

            if isinstance(line, KeyValueLine):
                if in_block and current_block is not None:
                    current_block["comments"].extend(pending)
                    pending.clear()
                    current_block["kvs"][line.keyword] = line.value
                else:
                    header_comments.extend(pending)
                    pending.clear()
                    header_kvs[line.keyword] = line.value
                continue

            if isinstance(line, DataLine):
                if in_block and current_block is not None:
                    current_block["data_lines"].append(line.text)
                continue

        if meta_block is None:
            raise ParseError("OCM/KVN: required META block not found.")

        header = OCM.Header(**map_kvs(header_kvs, header_comments, OCM.Header))
        metadata = OCM.Metadata(
            **map_kvs(meta_block["kvs"], meta_block["comments"], OCM.Metadata)
        )

        trajectory_states: list[OCM.TrajectoryStateTimeHistory] | None = [
            _parse_data_block(b, OCM.TrajectoryStateTimeHistory) for b in traj_blocks
        ] or None
        physical_characteristics: OCM.SpaceObjectPhysicalCharacteristics | None = (
            OCM.SpaceObjectPhysicalCharacteristics(
                **map_kvs(
                    phys_block["kvs"],
                    phys_block["comments"],
                    OCM.SpaceObjectPhysicalCharacteristics,
                )
            )
            if phys_block is not None
            else None
        )
        covariances: list[OCM.CovarianceTimeHistory] | None = [
            _parse_data_block(b, OCM.CovarianceTimeHistory) for b in cov_blocks
        ] or None
        maneuvers: list[OCM.ManeuverSpecification] | None = [
            _parse_data_block(b, OCM.ManeuverSpecification) for b in man_blocks
        ] or None
        perturbations: OCM.PerturbationsSpecification | None = (
            OCM.PerturbationsSpecification(
                **map_kvs(
                    pert_block["kvs"],
                    pert_block["comments"],
                    OCM.PerturbationsSpecification,
                )
            )
            if pert_block is not None
            else None
        )
        orbit_determination: OCM.OrbitDeterminationData | None = (
            OCM.OrbitDeterminationData(
                **map_kvs(
                    od_block["kvs"], od_block["comments"], OCM.OrbitDeterminationData
                )
            )
            if od_block is not None
            else None
        )
        user_defined: OCM.UserDefinedParameters | None = (
            OCM.UserDefinedParameters(
                **map_kvs(
                    user_block["kvs"], user_block["comments"], OCM.UserDefinedParameters
                )
            )
            if user_block is not None
            else None
        )

        return OCM(
            header=header,
            metadata=metadata,
            trajectory_states=trajectory_states,
            physical_characteristics=physical_characteristics,
            covariances=covariances,
            maneuvers=maneuvers,
            perturbations=perturbations,
            orbit_determination=orbit_determination,
            user_defined=user_defined,
        )

    def read(self, path: Path) -> OCM:
        return self._parse(path.read_text(encoding="utf-8"))

    def read_string(self, content: str) -> OCM:
        return self._parse(content)


OrbitComprehensiveMessageKVNReader = KVNOCMReader
