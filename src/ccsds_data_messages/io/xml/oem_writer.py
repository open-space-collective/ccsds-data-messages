"""
XML adapter: Orbit Ephemeris Message writer.

Produces OEM/XML per section 8.10.
Section 8.10.13: one <stateVector> per ephemeris data line.
Section 8.10.19: one <covarianceMatrix> per covariance epoch.
"""

from __future__ import annotations

# Build/serialize only in this module - parsing untrusted XML goes through
# io.xml.parser, which uses defusedxml.
import xml.etree.ElementTree as ET  # noqa: S405
from typing import TYPE_CHECKING

from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml._utils import _TAG_BODY
from ccsds_data_messages.io.xml._utils import _TAG_DATA
from ccsds_data_messages.io.xml._utils import build_ndm_root
from ccsds_data_messages.io.xml._utils import get_xml_tag
from ccsds_data_messages.io.xml._utils import serialize_xml
from ccsds_data_messages.io.xml._utils import write_model
from ccsds_data_messages.io.xml._utils import write_xml_file
from ccsds_data_messages.models.oem import OEM

if TYPE_CHECKING:
    from pathlib import Path


class XMLOEMWriter:
    """
    Write a validated OEM domain model to an OEM/XML file.

    Satisfies ``MessageWriterPort`` structurally.
    """

    def _build(
        self,
        message: OEM,
        *,
        options: WriterOptions | None = None,
    ) -> ET.Element:
        root: ET.Element = build_ndm_root(OEM, message.header)

        header_element: ET.Element = ET.SubElement(root, get_xml_tag(OEM.Header))
        write_model(
            message.header,
            header_element,
            skip_fields=frozenset({"ccsds_oem_vers"}),
            options=options,
        )

        body_element: ET.Element = ET.SubElement(root, _TAG_BODY)

        for segment in message.segments:
            segment_element: ET.Element = ET.SubElement(
                body_element, get_xml_tag(OEM.Segment)
            )
            metadata_element: ET.Element = ET.SubElement(
                segment_element, get_xml_tag(OEM.Segment.Metadata)
            )
            write_model(segment.metadata, metadata_element, options=options)

            data_element: ET.Element = ET.SubElement(segment_element, _TAG_DATA)

            # Section 7.8.9: comments at the beginning of the ephemeris data section.
            ephemeris_data: OEM.Segment.EphemerisData = segment.ephemeris_data
            if ephemeris_data.comment:
                for comment_text in ephemeris_data.comment:
                    ET.SubElement(data_element, "COMMENT").text = comment_text

            # Section 8.10.13: one <stateVector> per ephemeris data line.
            for state_vector_line in ephemeris_data.ephemeris_data_lines:
                state_vector_element: ET.Element = ET.SubElement(
                    data_element, get_xml_tag(OEM.Segment.EphemerisData.EphemerisDataLine)
                )
                write_model(state_vector_line, state_vector_element, options=options)

            # Section 8.10.19: one <covarianceMatrix> per covariance epoch.
            if segment.covariance_matrix is not None:
                covariance_matrix: OEM.Segment.CovarianceMatrix = (
                    segment.covariance_matrix
                )
                # Section 7.8.9: comments at the beginning of the covariance section.
                if covariance_matrix.comment:
                    for comment_text in covariance_matrix.comment:
                        ET.SubElement(data_element, "COMMENT").text = comment_text
                for covariance_matrix_line in covariance_matrix.covariance_matrix_lines:
                    covariance_matrix_element: ET.Element = ET.SubElement(
                        data_element,
                        get_xml_tag(OEM.Segment.CovarianceMatrix.CovarianceMatrixLines),
                    )
                    write_model(
                        covariance_matrix_line, covariance_matrix_element, options=options
                    )

        return root

    def write(
        self,
        message: OEM,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serialize a validated OEM domain model to an XML file at ``path``.

        Args:
            message (OEM): The validated OEM instance to serialize.
            path (Path): The destination file; created or overwritten.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        write_xml_file(self._build(message, options=options), path)

    def write_string(
        self,
        message: OEM,
        *,
        options: WriterOptions | None = None,
    ) -> str:
        """
        Serialize an OEM to an XML string without writing to disk.

        Args:
            message (OEM): The validated OEM instance to serialize.
            options (WriterOptions | None): The formatting options. When omitted, ``WriterOptions()`` defaults apply.

        Returns:
            str: The serialized content.
        """
        return serialize_xml(self._build(message, options=options))


OrbitEphemerisMessageXMLWriter = XMLOEMWriter
