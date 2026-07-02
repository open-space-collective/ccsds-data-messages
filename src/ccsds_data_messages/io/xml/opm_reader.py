"""
XML adapter: Orbit Parameter Message reader.

OPM/XML structure (section 8.8, table 8-3, Annex G fig G-5):

  <opm id="CCSDS_OPM_VERS" version="3.0">
    <header> ... </header>
    <body>
      <segment>
        <metadata> ... </metadata>
        <data>
          <stateVector> ... </stateVector>
          <keplerianElements> ... </keplerianElements>   (optional)
          <spacecraftParameters> ... </spacecraftParameters> (optional)
          <covarianceMatrix> ... </covarianceMatrix>      (optional)
          <maneuverParameters> ... </maneuverParameters>  (optional, repeatable)
          <userDefinedParameters> ... </userDefinedParameters> (optional)
        </data>
      </segment>
    </body>
  </opm>

Spec references:
- Section 8.1: ODM keyword elements use all-caps names (same as KVN keywords).
- Section 8.3.6: version number is the root ``version`` attribute, not a child element.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ccsds_data_messages.io.xml._utils import _TAG_BODY
from ccsds_data_messages.io.xml._utils import _TAG_SEGMENT
from ccsds_data_messages.io.xml._utils import get_xml_tag
from ccsds_data_messages.io.xml._utils import read_model
from ccsds_data_messages.io.xml.parser import find_all
from ccsds_data_messages.io.xml.parser import find_child
from ccsds_data_messages.io.xml.parser import parse_xml_file
from ccsds_data_messages.io.xml.parser import parse_xml_string
from ccsds_data_messages.models.opm import OPM

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET
    from pathlib import Path


class XMLOPMReader:
    """
    Read an OPM/XML file and return a validated OPM domain model.

    Satisfies ``MessageReaderPort`` structurally.
    """

    def _parse(
        self,
        root: ET.Element,
    ) -> OPM:
        # Section 8.3.6: version is the root ``version`` attribute.
        version: str = root.attrib.get("version", "3.0")

        header_element: ET.Element | None = find_child(root, get_xml_tag(OPM.Header))
        segment_element: ET.Element | None = find_child(
            find_child(root, _TAG_BODY), _TAG_SEGMENT
        )
        metadata_element: ET.Element | None = find_child(
            segment_element, get_xml_tag(OPM.Metadata)
        )
        data_element: ET.Element | None = find_child(
            segment_element, get_xml_tag(OPM.Data)
        )

        header: OPM.Header = OPM.Header(
            **read_model(
                header_element,
                OPM.Header,
                extra_kvs={"CCSDS_OPM_VERS": version},
            )
        )
        metadata: OPM.Metadata = OPM.Metadata(
            **read_model(metadata_element, OPM.Metadata)
        )

        state_vector_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OPM.Data.StateVector)
        )
        state_vector: OPM.Data.StateVector = OPM.Data.StateVector(
            **read_model(state_vector_element, OPM.Data.StateVector)
        )

        osculating_keplerian_elements_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OPM.Data.OsculatingKeplerianElements)
        )
        keplerian: OPM.Data.OsculatingKeplerianElements | None = (
            OPM.Data.OsculatingKeplerianElements(
                **read_model(
                    osculating_keplerian_elements_element,
                    OPM.Data.OsculatingKeplerianElements,
                )
            )
            if osculating_keplerian_elements_element is not None
            else None
        )

        spacecraft_parameters_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OPM.Data.SpacecraftParameters)
        )
        spacecraft: OPM.Data.SpacecraftParameters | None = (
            OPM.Data.SpacecraftParameters(
                **read_model(spacecraft_parameters_element, OPM.Data.SpacecraftParameters)
            )
            if spacecraft_parameters_element is not None
            else None
        )

        covariance_matrix_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OPM.Data.CovarianceMatrix)
        )
        cov: OPM.Data.CovarianceMatrix | None = (
            OPM.Data.CovarianceMatrix(
                **read_model(covariance_matrix_element, OPM.Data.CovarianceMatrix)
            )
            if covariance_matrix_element is not None
            else None
        )

        maneuver_parameters_elements: list[ET.Element] = find_all(
            data_element, get_xml_tag(OPM.Data.ManeuverParameters)
        )
        maneuvers: list[OPM.Data.ManeuverParameters] | None = [
            OPM.Data.ManeuverParameters(
                **read_model(element, OPM.Data.ManeuverParameters)
            )
            for element in maneuver_parameters_elements
        ] or None

        user_defined_parameters_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OPM.Data.UserDefinedParameters)
        )
        user: OPM.Data.UserDefinedParameters | None = (
            OPM.Data.UserDefinedParameters(
                **read_model(
                    user_defined_parameters_element, OPM.Data.UserDefinedParameters
                )
            )
            if user_defined_parameters_element is not None
            else None
        )

        data: OPM.Data = OPM.Data(
            state_vector=state_vector,
            osculating_keplerian_elements=keplerian,
            spacecraft_parameters=spacecraft,
            covariance_matrix=cov,
            maneuvers=maneuvers,
            user_defined=user,
        )
        return OPM(
            header=header,
            metadata=metadata,
            data=data,
        )

    def read(
        self,
        path: Path,
    ) -> OPM:
        """
        Read an OPM/XML file and return a validated ``OPM`` domain model.

        Args:
            path (Path): The path to the XML OPM file.

        Returns:
            OPM: Fully validated OPM domain model.

        Raises:
            pydantic.ValidationError: If the parsed content fails domain model
                validation.
        """
        return self._parse(parse_xml_file(path))

    def read_string(
        self,
        content: str,
    ) -> OPM:
        """
        Read an OPM/XML string and return a validated OPM domain model.

        Args:
            content (str): The OPM/XML string to read.

        Returns:
            OPM: Fully validated OPM domain model.
        """
        return self._parse(parse_xml_string(content))


OrbitParameterMessageXMLReader = XMLOPMReader
