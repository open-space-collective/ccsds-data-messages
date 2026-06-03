"""
All keyword strings are read from ``FieldMetadata`` annotations on the OCM domain
model: none are hardcoded. Block delimiter names are derived from the
``Delineation`` private attributes on the relevant nested classes.

Spec references:
- Section 6.2 (OCM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.8.10 (comments)
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from orbit_data_messages.io.kvn._utils import block_delimiter_name
from orbit_data_messages.io.kvn._utils import map_kvs
from orbit_data_messages.io.kvn.parser import parse_kvn
from orbit_data_messages.io.kvn.parser import split_blocks
from orbit_data_messages.models.ocm import OCM

if TYPE_CHECKING:
    from pydantic import BaseModel

# All block delimiter names come from ``Delineation`` on the model classes
# no *_START or *_STOP string literals appear in this adapter.
_META_D: str = block_delimiter_name(OCM.Metadata)                              # "META"
_TRAJ_D: str = block_delimiter_name(OCM.TrajectoryStateTimeHistory)            # "TRAJ"
_PHYS_D: str = block_delimiter_name(OCM.SpaceObjectPhysicalCharacteristics)    # "PHYS"
_COV_D: str  = block_delimiter_name(OCM.CovarianceTimeHistory)                 # "COV"
_MAN_D: str  = block_delimiter_name(OCM.ManeuverSpecification)                 # "MAN"
_PERT_D: str = block_delimiter_name(OCM.PerturbationsSpecification)            # "PERT"
_OD_D: str   = block_delimiter_name(OCM.OrbitDeterminationData)                # "OD"
_USER_D: str = block_delimiter_name(OCM.UserDefinedParameters)                 # "USER"


def _parse_data_block(
    block: dict[str, Any],
    model_class: type[BaseModel],
) -> BaseModel:
    """
    Parse a named OCM data block that carries both KV metadata and raw data lines.

    Handles ``TRAJ`` (section 7.4.1.5), ``COV`` (section 7.4.1.6), and ``MAN`` (section 7.4.1.7)
    blocks. The resulting model's ``data_lines`` attribute holds the raw
    whitespace-separated lines that follow the KV section within the block.

    Args:
        block (dict[str, Any]): Parsed block dict from ``split_blocks()``,
            containing ``kvs``, ``comments``, and ``data_lines``.
        model_class (type[BaseModel]): Target model class to instantiate
            (e.g. ``OCM.TrajectoryStateTimeHistory``).

    Returns:
        BaseModel: Validated instance of ``model_class``.
    """
    kwargs: dict[str, Any] = map_kvs(block["kvs"], block["comments"], model_class)
    kwargs["data_lines"] = block.get("data_lines") or []
    return model_class(**kwargs)


class KVNOCMReader:
    """
    Read a KVN-format OCM file and return a validated OCM domain model.

    Satisfies ``MessageReaderPort`` structurally. ``pydantic.ValidationError`` is
    never swallowed: let it propagate to the caller.
    """

    def _parse(
        self,
        text: str,
    ) -> OCM:
        """
        Parse a KVN-format OCM file and return a validated OCM domain model.

        Args:
            text (str): The KVN-format OCM file content.

        Returns:
            OCM: Fully validated OCM domain model.

        Raises:
            ValueError: If the required ``META`` block is missing.
            pydantic.ValidationError: If the parsed content fails domain model
                validation.
        """
        raw: dict[str, Any] = parse_kvn(text)
        sections: list[dict[str, Any]] = split_blocks(raw)

        # Header
        header_sec: dict[str, Any] = sections[0]
        header: OCM.Header = OCM.Header(
            **map_kvs(header_sec["kvs"], header_sec["comments"], OCM.Header)
        )

        # Collect named blocks by their delimiter type.
        meta_block: dict[str, Any] | None = None
        traj_blocks: list[dict[str, Any]] = []
        phys_block: dict[str, Any] | None = None
        cov_blocks: list[dict[str, Any]] = []
        man_blocks: list[dict[str, Any]] = []
        pert_block: dict[str, Any] | None = None
        od_block: dict[str, Any] | None = None
        user_block: dict[str, Any] | None = None

        for section in sections[1:]:
            if section["type"] != "block":
                continue
            delimiter: str = section["delimiter"]
            if delimiter == _META_D:
                meta_block = section
            elif delimiter == _TRAJ_D:
                traj_blocks.append(section)
            elif delimiter == _PHYS_D:
                phys_block = section
            elif delimiter == _COV_D:
                cov_blocks.append(section)
            elif delimiter == _MAN_D:
                man_blocks.append(section)
            elif delimiter == _PERT_D:
                pert_block = section
            elif delimiter == _OD_D:
                od_block = section
            elif delimiter == _USER_D:
                user_block = section

        if meta_block is None:
            raise ValueError("OCM/KVN: required ``META`` block not found.")

        metadata: OCM.Metadata = OCM.Metadata(
            **map_kvs(
                meta_block["kvs"],
                meta_block["comments"],
                OCM.Metadata,
            )
        )

        trajectory_states: list[OCM.TrajectoryStateTimeHistory] | None = (
            [_parse_data_block(block, OCM.TrajectoryStateTimeHistory) for block in traj_blocks] or None
        )

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

        # Section 6.2.7.3: covariance blocks are repeatable.
        covariances: list[OCM.CovarianceTimeHistory] | None = (
            [_parse_data_block(block, OCM.CovarianceTimeHistory) for block in cov_blocks] or None
        )

        # Section 6.2.8.4: maneuver blocks are repeatable.
        maneuvers: list[OCM.ManeuverSpecification] | None = (
            [_parse_data_block(block, OCM.ManeuverSpecification) for block in man_blocks] or None
        )

        # Section 6.2.9.2: perturbations block is at most one.
        perturbations: OCM.PerturbationsSpecification | None = (
            OCM.PerturbationsSpecification(
                **map_kvs(pert_block["kvs"], pert_block["comments"],
                          OCM.PerturbationsSpecification,
                )
            )
            if pert_block is not None
            else None
        )

        # Section 6.2.10.2: orbit determination block is at most one.
        orbit_determination: OCM.OrbitDeterminationData | None = (
            OCM.OrbitDeterminationData(
                **map_kvs(
                    od_block["kvs"],
                    od_block["comments"],
                    OCM.OrbitDeterminationData,
                )
            )
            if od_block is not None
            else None
        )

        # Section 6.2.11.2: user defined parameters block is at most one.
        user_defined: OCM.UserDefinedParameters | None = (
            OCM.UserDefinedParameters(
                **map_kvs(
                    user_block["kvs"],
                    user_block["comments"],
                    OCM.UserDefinedParameters,
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

    def read(
        self,
        path: Path,
    ) -> OCM:
        """
        Read a KVN OCM file and return a validated `OCM` domain model.

        Args:
            path (Path): The path to the KVN OCM file.

        Returns:
            OCM: Validated OCM domain model.
        """
        return self._parse(path.read_text())

    def read_string(
        self,
        content: str,
    ) -> OCM:
        """
        Read an OCM KVN string and return a validated OCM domain model.

        Args:
            content (str): The KVN-format OCM file content.

        Returns:
            OCM: Validated OCM domain model.
        """
        return self._parse(content)


OrbitComprehensiveMessageKVNReader = KVNOCMReader
