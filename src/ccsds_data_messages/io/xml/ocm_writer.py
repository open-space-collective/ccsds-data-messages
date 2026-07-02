"""
XML adapter: Orbit Comprehensive Message writer.

Produces OCM/XML per section 8.11, table 8-9.
Section 8.11.15: trajLine / covLine / manLine elements hold raw data strings.
"""

from __future__ import annotations

# Build/serialize only in this module - parsing untrusted XML goes through
# io.xml.parser, which uses defusedxml.
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import replace
from typing import TYPE_CHECKING

from ccsds_data_messages.io._ocm_maneuver import serialize_maneuver_rows
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml._utils import _TAG_BODY
from ccsds_data_messages.io.xml._utils import _TAG_DATA
from ccsds_data_messages.io.xml._utils import _TAG_SEGMENT
from ccsds_data_messages.io.xml._utils import build_ndm_root
from ccsds_data_messages.io.xml._utils import get_xml_line_tag
from ccsds_data_messages.io.xml._utils import get_xml_tag
from ccsds_data_messages.io.xml._utils import serialize_xml
from ccsds_data_messages.io.xml._utils import write_model
from ccsds_data_messages.io.xml._utils import write_xml_file
from ccsds_data_messages.models.ocm import OCM

if TYPE_CHECKING:
    from pathlib import Path

# The 3 OCM block types with raw data lines (section 8.11.15). A Protocol can't
# express "BaseModel with a data_lines attribute" (mypy rejects protocols that
# inherit from a concrete class), so this lists the actual types by name instead -
# adding a 4th data-lines-bearing block type means extending this alias explicitly.
_BlockWithLines = (
    OCM.TrajectoryStateTimeHistory | OCM.CovarianceTimeHistory | OCM.ManeuverSpecification
)


def _write_block_with_lines(
    block: _BlockWithLines,
    data_element: ET.Element,
    *,
    options: WriterOptions | None = None,
) -> None:
    """
    Write keyword child elements and raw data line elements for an OCM block.

    Creates a child element under ``data_el`` whose tag is derived from
    ``block._xml_tag``, writes keyword elements via ``write_model``, then
    appends one data-line element per raw string (section 8.11.15). The
    data-line tag is derived from ``block._xml_line_tag``.

    Args:
        block: The OCM data block model (one of the 3 types with raw data lines)
            whose ``data_lines`` attribute holds the raw strings.
        data_el (ET.Element): The parent ``<data>`` XML element.
        options (WriterOptions | None): The writer options. Defaults to None.

    Returns:
        None
    """
    section_element: ET.Element = ET.SubElement(data_element, get_xml_tag(type(block)))
    write_model(block, section_element, options=options)
    # Section 8.11.15: each raw data string becomes its own line element. Maneuver
    # rows are typed and serialized here; trajectory/covariance rows are raw strings.
    lines: list[str] = (
        serialize_maneuver_rows(
            block.man_composition,
            block.data_lines,
            options.float_formats if options is not None else None,
        )
        if isinstance(block, OCM.ManeuverSpecification)
        else block.data_lines
    )
    for line in lines:
        ET.SubElement(section_element, get_xml_line_tag(type(block))).text = line


class XMLOCMWriter:
    """
    Write a validated OCM domain model to an OCM/XML file.

    Satisfies ``MessageWriterPort`` structurally.
    """

    def _build(
        self,
        message: OCM,
        *,
        options: WriterOptions | None = None,
    ) -> ET.Element:
        # OCM default: suppress spec-default-valued fields so output matches the OCM
        # fixtures, unless the caller set suppress_defaults explicitly.
        base = options if options is not None else WriterOptions()
        effective_options = (
            base
            if base.suppress_defaults is not None
            else replace(base, suppress_defaults=True)
        )

        root: ET.Element = build_ndm_root(OCM, message.header)

        header_element: ET.Element = ET.SubElement(root, get_xml_tag(OCM.Header))
        write_model(
            message.header,
            header_element,
            skip_fields=frozenset({"ccsds_ocm_vers"}),
            options=effective_options,
        )

        body_element: ET.Element = ET.SubElement(root, _TAG_BODY)
        segment_element: ET.Element = ET.SubElement(body_element, _TAG_SEGMENT)
        metadata_element: ET.Element = ET.SubElement(
            segment_element, get_xml_tag(OCM.Metadata)
        )
        write_model(message.metadata, metadata_element, options=effective_options)

        data_element: ET.Element = ET.SubElement(segment_element, _TAG_DATA)

        if message.trajectory_states:
            for traj_block in message.trajectory_states:
                _write_block_with_lines(
                    traj_block, data_element, options=effective_options
                )

        if message.physical_characteristics is not None:
            phys_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OCM.SpaceObjectPhysicalCharacteristics)
            )
            write_model(
                message.physical_characteristics, phys_element, options=effective_options
            )

        if message.covariances:
            for cov_block in message.covariances:
                _write_block_with_lines(
                    cov_block, data_element, options=effective_options
                )

        if message.maneuvers:
            for man_block in message.maneuvers:
                _write_block_with_lines(
                    man_block, data_element, options=effective_options
                )

        if message.perturbations is not None:
            pert_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OCM.PerturbationsSpecification)
            )
            write_model(message.perturbations, pert_element, options=effective_options)

        if message.orbit_determination is not None:
            od_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OCM.OrbitDeterminationData)
            )
            write_model(
                message.orbit_determination, od_element, options=effective_options
            )

        if message.user_defined is not None:
            user_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OCM.UserDefinedParameters)
            )
            write_model(message.user_defined, user_element, options=effective_options)

        return root

    def write(
        self,
        message: OCM,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serialize a validated OCM domain model to an XML file at ``path``.

        Args:
            message (OCM): The validated OCM instance to serialize.
            path (Path): The destination file; created or overwritten.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        write_xml_file(self._build(message, options=options), path)

    def write_string(
        self,
        message: OCM,
        *,
        options: WriterOptions | None = None,
    ) -> str:
        """
        Serialize a validated OCM domain model to an XML string without writing to disk.

        Args:
            message (OCM): The validated OCM instance to serialize.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.

        Returns:
            str: The serialized content.
        """
        return serialize_xml(self._build(message, options=options))


OrbitComprehensiveMessageXMLWriter = XMLOCMWriter
