"""
XML adapter: Orbit Mean-Elements Message writer.

Produces OMM/XML per section 8.9, table 8-5.
"""

from __future__ import annotations

# Build/serialize only in this module - parsing untrusted XML goes through
# io.xml.parser, which uses defusedxml.
import xml.etree.ElementTree as ET  # noqa: S405
from typing import TYPE_CHECKING

from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml._utils import (
    _TAG_BODY,
    _TAG_SEGMENT,
    get_xml_tag,
    serialize_xml,
    write_model,
    write_xml_file,
)
from ccsds_data_messages.models.omm import OMM

if TYPE_CHECKING:
    from pathlib import Path

_XMLNS_XSI: str = "http://www.w3.org/2001/XMLSchema-instance"
_NDM_SCHEMA: str = (
    "https://sanaregistry.org/r/ndmxml_unqualified/ndmxml-3.0.0-master-3.0.xsd"
)


class XMLOMMWriter:
    """
    Write a validated OMM domain model to an OMM/XML file.

    Satisfies ``MessageWriterPort`` structurally.
    """

    def _build(
        self,
        message: OMM,
        *,
        options: WriterOptions | None = None,
    ) -> ET.Element:
        root: ET.Element = ET.Element(get_xml_tag(OMM))
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("xsi:noNamespaceSchemaLocation", _NDM_SCHEMA)
        root.set("id", "CCSDS_OMM_VERS")
        root.set("version", message.header.ccsds_omm_vers)

        header_element: ET.Element = ET.SubElement(root, get_xml_tag(OMM.Header))
        write_model(
            message.header,
            header_element,
            skip_fields=frozenset({"ccsds_omm_vers"}),
            options=options,
        )

        body_element: ET.Element = ET.SubElement(root, _TAG_BODY)
        segment_element: ET.Element = ET.SubElement(body_element, _TAG_SEGMENT)
        metadata_element: ET.Element = ET.SubElement(
            segment_element, get_xml_tag(OMM.Metadata)
        )
        write_model(message.metadata, metadata_element, options=options)

        data_element: ET.Element = ET.SubElement(segment_element, get_xml_tag(OMM.Data))

        mean_keplerian_elements_element: ET.Element = ET.SubElement(
            data_element, get_xml_tag(OMM.Data.MeanKeplerianElements)
        )
        write_model(
            message.data.mean_keplerian_elements,
            mean_keplerian_elements_element,
            options=options,
        )

        if message.data.spacecraft_parameters is not None:
            spacecraft_parameters_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OMM.Data.SpacecraftParameters)
            )
            write_model(
                message.data.spacecraft_parameters,
                spacecraft_parameters_element,
                options=options,
            )

        if message.data.tle_related_parameters is not None:
            tle_related_parameters_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OMM.Data.TLERelatedParameters)
            )
            write_model(
                message.data.tle_related_parameters,
                tle_related_parameters_element,
                options=options,
            )

        if message.data.covariance_matrix is not None:
            covariance_matrix_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OMM.Data.CovarianceMatrix)
            )
            write_model(
                message.data.covariance_matrix, covariance_matrix_element, options=options
            )

        if message.data.user_defined is not None:
            user_defined_parameters_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OMM.Data.UserDefinedParameters)
            )
            write_model(
                message.data.user_defined,
                user_defined_parameters_element,
                options=options,
            )

        return root

    def write(
        self,
        message: OMM,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serialize a validated OMM domain model to an XML file at ``path``.

        Args:
            message (OMM): The validated OMM instance to serialize.
            path (Path): The destination file; created or overwritten.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        write_xml_file(self._build(message, options=options), path)

    def write_string(
        self,
        message: OMM,
        *,
        options: WriterOptions | None = None,
    ) -> str:
        """
        Serialize a validated OMM domain model to an XML string without writing to disk.

        Args:
            message (OMM): The validated OMM instance to serialize.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.

        Returns:
            str: The serialized content.
        """
        return serialize_xml(self._build(message, options=options))


OrbitMeanElementsMessageXMLWriter = XMLOMMWriter
