"""
XML adapter: Orbit Parameter Message writer.

Produces OPM/XML per section 8.8, table 8-3, Annex G fig G-5.
Keyword element names come from FieldMetadata: nothing hardcoded.
"""

from __future__ import annotations

# Build/serialize only in this module - parsing untrusted XML goes through
# io.xml.parser, which uses defusedxml.
import xml.etree.ElementTree as ET  # noqa: S405
from typing import TYPE_CHECKING

from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml._utils import _TAG_BODY
from ccsds_data_messages.io.xml._utils import _TAG_SEGMENT
from ccsds_data_messages.io.xml._utils import build_ndm_root
from ccsds_data_messages.io.xml._utils import get_xml_tag
from ccsds_data_messages.io.xml._utils import serialize_xml
from ccsds_data_messages.io.xml._utils import write_model
from ccsds_data_messages.io.xml._utils import write_xml_file
from ccsds_data_messages.models.opm import OPM

if TYPE_CHECKING:
    from pathlib import Path


class XMLOPMWriter:
    """
    Write a validated OPM domain model to an OPM/XML file.

    Satisfies ``MessageWriterPort`` structurally.
    """

    def _build(
        self,
        message: OPM,
        *,
        options: WriterOptions | None = None,
    ) -> ET.Element:
        root: ET.Element = build_ndm_root(OPM, message.header)

        header_element: ET.Element = ET.SubElement(root, get_xml_tag(OPM.Header))
        write_model(
            message.header,
            header_element,
            skip_fields=frozenset({"ccsds_opm_vers"}),
            options=options,
        )

        body_element: ET.Element = ET.SubElement(root, _TAG_BODY)
        segment_element: ET.Element = ET.SubElement(body_element, _TAG_SEGMENT)
        metadata_element: ET.Element = ET.SubElement(
            segment_element, get_xml_tag(OPM.Metadata)
        )
        write_model(message.metadata, metadata_element, options=options)

        data_element: ET.Element = ET.SubElement(segment_element, get_xml_tag(OPM.Data))

        state_vector_element: ET.Element = ET.SubElement(
            data_element, get_xml_tag(OPM.Data.StateVector)
        )
        write_model(message.data.state_vector, state_vector_element, options=options)

        if message.data.osculating_keplerian_elements is not None:
            osculating_keplerian_elements_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OPM.Data.OsculatingKeplerianElements)
            )
            write_model(
                message.data.osculating_keplerian_elements,
                osculating_keplerian_elements_element,
                options=options,
            )

        if message.data.spacecraft_parameters is not None:
            spacecraft_parameters_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OPM.Data.SpacecraftParameters)
            )
            write_model(
                message.data.spacecraft_parameters,
                spacecraft_parameters_element,
                options=options,
            )

        if message.data.covariance_matrix is not None:
            covariance_matrix_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OPM.Data.CovarianceMatrix)
            )
            write_model(
                message.data.covariance_matrix, covariance_matrix_element, options=options
            )

        if message.data.maneuvers:
            for maneuver in message.data.maneuvers:
                maneuver_parameters_element: ET.Element = ET.SubElement(
                    data_element, get_xml_tag(OPM.Data.ManeuverParameters)
                )
                write_model(maneuver, maneuver_parameters_element, options=options)

        if message.data.user_defined is not None:
            user_defined_parameters_element: ET.Element = ET.SubElement(
                data_element, get_xml_tag(OPM.Data.UserDefinedParameters)
            )
            write_model(
                message.data.user_defined,
                user_defined_parameters_element,
                options=options,
            )

        return root

    def write(
        self,
        message: OPM,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serialize a validated OPM domain model to an XML file at ``path``.

        Args:
            message (OPM): The validated OPM instance to serialize.
            path (Path): The destination file; created or overwritten.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        write_xml_file(self._build(message, options=options), path)

    def write_string(
        self,
        message: OPM,
        *,
        options: WriterOptions | None = None,
    ) -> str:
        """
        Serialize a validated OPM domain model to an XML string without writing to disk.

        Args:
            message (OPM): The validated OPM instance to serialize.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.

        Returns:
            str: The serialized content.
        """
        return serialize_xml(self._build(message, options=options))


OrbitParameterMessageXMLWriter = XMLOPMWriter
