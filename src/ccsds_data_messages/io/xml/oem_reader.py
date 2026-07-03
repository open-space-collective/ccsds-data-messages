"""
XML adapter: Orbit Ephemeris Message reader.

OEM/XML structure (section 8.10):

  <oem id="CCSDS_OEM_VERS" version="3.0">
    <header> ... </header>
    <body>
      <segment>+                          (one or more)
        <metadata> ... </metadata>
        <data>
          <stateVector>+                  (one per ephemeris epoch, section 8.10.13)
            <EPOCH>...</EPOCH>
            <X units="km">...</X>
            ...
          </stateVector>
          <covarianceMatrix>*             (zero or more, section 8.10.19)
            <EPOCH>...</EPOCH>
            <COV_REF_FRAME>...</COV_REF_FRAME>
            <CX_X units="km**2">...</CX_X>
            ...
          </covarianceMatrix>
        </data>
      </segment>
    </body>
  </oem>

Spec references:
- Section 8.1: ODM keyword elements use all-caps names.
- Section 8.10.13: <stateVector> wraps one ephemeris data line.
- Section 8.10.19: <covarianceMatrix> wraps one covariance matrix epoch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io.xml._utils import _TAG_BODY
from ccsds_data_messages.io.xml._utils import _TAG_DATA
from ccsds_data_messages.io.xml._utils import get_xml_tag
from ccsds_data_messages.io.xml._utils import read_model
from ccsds_data_messages.io.xml.parser import find_all
from ccsds_data_messages.io.xml.parser import find_child
from ccsds_data_messages.io.xml.parser import parse_xml_file
from ccsds_data_messages.io.xml.parser import parse_xml_string
from ccsds_data_messages.io.xml.parser import strip_ns
from ccsds_data_messages.models.oem import OEM

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET
    from pathlib import Path


class XMLOEMReader:
    """
    Read an OEM/XML file and return a validated OEM domain model.

    Satisfies ``MessageReaderPort`` structurally.
    """

    def _parse(self, root: ET.Element) -> OEM:
        version: str = root.attrib.get("version", "3.0")

        header_element: ET.Element | None = find_child(root, get_xml_tag(OEM.Header))
        body_element: ET.Element | None = find_child(root, _TAG_BODY)

        header: OEM.Header = OEM.Header(
            **read_model(
                header_element,
                OEM.Header,
                extra_kvs={"CCSDS_OEM_VERS": version},
            )
        )

        segments: list[OEM.Segment] = []
        for segment_element in find_all(body_element, get_xml_tag(OEM.Segment)):
            metadata_element: ET.Element | None = find_child(
                segment_element, get_xml_tag(OEM.Segment.Metadata)
            )
            if (data_element := find_child(segment_element, _TAG_DATA)) is None:
                raise ParseError(
                    "OEM/XML: segment has no <data> element (section 5.2.4.1)."
                )

            metadata: OEM.Segment.Metadata = OEM.Segment.Metadata(
                **read_model(metadata_element, OEM.Segment.Metadata)
            )

            state_vector_tag: str = get_xml_tag(
                OEM.Segment.EphemerisData.EphemerisDataLine
            )
            covariance_matrix_tag: str = get_xml_tag(
                OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
            )

            # Section 7.8.9: collect <COMMENT> elements that precede the first
            # <stateVector> for EphemerisData.comment, and those that precede
            # the first <covarianceMatrix> (after the stateVectors) for
            # CovarianceMatrix.comment.
            ephemeris_data_comments: list[str] = []
            covariance_matrix_comments: list[str] = []
            phase: str = (
                "ephem"  # 'ephem' -> before stateVectors; 'cov' -> between SV/COV
            )

            for child in data_element:
                tag: str = strip_ns(child.tag)
                if tag == state_vector_tag:
                    phase = "cov"
                elif tag == covariance_matrix_tag:
                    break
                elif tag == "COMMENT":
                    if phase == "ephem":
                        ephemeris_data_comments.append((child.text or "").strip())
                    else:
                        covariance_matrix_comments.append((child.text or "").strip())

            # Section 8.10.13: one <stateVector> per ephemeris epoch.
            state_vector_lines: list[OEM.Segment.EphemerisData.EphemerisDataLine] = [
                OEM.Segment.EphemerisData.EphemerisDataLine(
                    **read_model(
                        state_vector_element, OEM.Segment.EphemerisData.EphemerisDataLine
                    )
                )
                for state_vector_element in find_all(data_element, state_vector_tag)
            ]
            ephemeris_data: OEM.Segment.EphemerisData = OEM.Segment.EphemerisData(
                comment=ephemeris_data_comments or None,
                ephemeris_data_lines=state_vector_lines,
            )

            # Section 8.10.19: zero or more <covarianceMatrix> elements.
            _CovarianceMatrixLines = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
            covariance_matrix_lines_list: list[
                OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
            ] = [
                _CovarianceMatrixLines(
                    **read_model(covariance_matrix_element, _CovarianceMatrixLines)
                )
                for covariance_matrix_element in find_all(
                    data_element, covariance_matrix_tag
                )
            ]
            covariance_matrix: OEM.Segment.CovarianceMatrix | None = (
                OEM.Segment.CovarianceMatrix(
                    comment=covariance_matrix_comments or None,
                    covariance_matrix_lines=covariance_matrix_lines_list,
                )
                if covariance_matrix_lines_list
                else None
            )

            segments.append(
                OEM.Segment(
                    metadata=metadata,
                    ephemeris_data=ephemeris_data,
                    covariance_matrix=covariance_matrix,
                )
            )

        return OEM(
            header=header,
            segments=segments,
        )

    def read(
        self,
        path: Path,
    ) -> OEM:
        """
        Read an OEM/XML file and return a validated ``OEM`` domain model.

        Args:
            path (Path): The path to the XML OEM file.

        Returns:
            OEM: Fully validated OEM domain model.

        Raises:
            pydantic.ValidationError: If the parsed content fails domain model
                validation.
        """
        return self._parse(parse_xml_file(path))

    def read_string(
        self,
        content: str,
    ) -> OEM:
        """
        Read an OEM/XML string and return a validated OEM domain model.

        Args:
            content (str): The OEM/XML string to read.

        Returns:
            OEM: Fully validated OEM domain model.
        """
        return self._parse(parse_xml_string(content))


OrbitEphemerisMessageXMLReader = XMLOEMReader
