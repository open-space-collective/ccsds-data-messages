"""
XML adapter: Orbit Comprehensive Message writer.

Produces OCM/XML per section 8.11, table 8-9.
section 8.11.15: trajLine / covLine / manLine elements hold raw data strings.
"""

from __future__ import annotations

# Build/serialize only in this module - parsing untrusted XML goes through
# io.xml.parser, which uses defusedxml.
import xml.etree.ElementTree as ET  # noqa: S405
from typing import TYPE_CHECKING

from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml._utils import (
    _TAG_BODY,
    _TAG_DATA,
    _TAG_SEGMENT,
    get_xml_line_tag,
    get_xml_tag,
    serialize_xml,
    write_model,
    write_xml_file,
)
from ccsds_data_messages.models.ocm import OCM

if TYPE_CHECKING:
    from pathlib import Path

_XMLNS_XSI: str = "http://www.w3.org/2001/XMLSchema-instance"
_NDM_SCHEMA: str = (
    "https://sanaregistry.org/r/ndmxml_unqualified/ndmxml-3.0.0-master-3.0.xsd"
)

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
    # section 8.11.15: each raw data string becomes its own line element.
    for line in block.data_lines:
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
        # OCM default: suppress default-valued fields so output matches spec fixtures.
        effective_options = (
            options if options is not None else WriterOptions(suppress_defaults=True)
        )

        root: ET.Element = ET.Element(get_xml_tag(OCM))
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("xsi:noNamespaceSchemaLocation", _NDM_SCHEMA)
        root.set("id", "CCSDS_OCM_VERS")
        root.set("version", message.header.ccsds_ocm_vers)

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
