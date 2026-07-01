"""
XML adapter: Orbit Mean-Elements Message reader.

OMM/XML structure (section 8.9, table 8-5):

  <omm id="CCSDS_OMM_VERS" version="3.0">
    <header> ... </header>
    <body>
      <segment>
        <metadata> ... </metadata>
        <data>
          <meanElements> ... </meanElements>
          <spacecraftParameters> ... </spacecraftParameters>  (optional)
          <tleParameters> ... </tleParameters>               (optional)
          <covarianceMatrix> ... </covarianceMatrix>          (optional)
          <userDefinedParameters> ... </userDefinedParameters> (optional)
        </data>
      </segment>
    </body>
  </omm>

Spec references:
- Section 8.1: ODM keyword elements use all-caps names.
- Section 8.3.6: version number is the root 'version' attribute.
- Section 4.2.4.8: maneuvers not accommodated in OMM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ccsds_data_messages.io.xml._utils import (
    _TAG_BODY,
    _TAG_SEGMENT,
    get_xml_tag,
    read_model,
)
from ccsds_data_messages.io.xml.parser import find_child, parse_xml_file, parse_xml_string
from ccsds_data_messages.models.omm import OMM

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET
    from pathlib import Path


class XMLOMMReader:
    """
    Read an OMM/XML file and return a validated OMM domain model.

    Satisfies ``MessageReaderPort`` structurally.
    """

    def _parse(self, root: ET.Element) -> OMM:
        version: str = root.attrib.get("version", "3.0")

        header_element: ET.Element | None = find_child(root, get_xml_tag(OMM.Header))
        segment_element: ET.Element | None = find_child(
            find_child(root, _TAG_BODY), _TAG_SEGMENT
        )
        metadata_element: ET.Element | None = find_child(
            segment_element, get_xml_tag(OMM.Metadata)
        )
        data_element: ET.Element | None = find_child(
            segment_element, get_xml_tag(OMM.Data)
        )

        header: OMM.Header = OMM.Header(
            **read_model(
                header_element,
                OMM.Header,
                extra_kvs={"CCSDS_OMM_VERS": version},
            )
        )
        metadata: OMM.Metadata = OMM.Metadata(
            **read_model(metadata_element, OMM.Metadata)
        )

        mean_keplerian_elements_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OMM.Data.MeanKeplerianElements)
        )
        mean_keplerian: OMM.Data.MeanKeplerianElements = OMM.Data.MeanKeplerianElements(
            **read_model(mean_keplerian_elements_element, OMM.Data.MeanKeplerianElements)
        )

        spacecraft_parameters_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OMM.Data.SpacecraftParameters)
        )
        spacecraft: OMM.Data.SpacecraftParameters | None = (
            OMM.Data.SpacecraftParameters(
                **read_model(spacecraft_parameters_element, OMM.Data.SpacecraftParameters)
            )
            if spacecraft_parameters_element is not None
            else None
        )

        tle_related_parameters_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OMM.Data.TLERelatedParameters)
        )
        tle_related_parameters: OMM.Data.TLERelatedParameters | None = (
            OMM.Data.TLERelatedParameters(
                **read_model(
                    tle_related_parameters_element, OMM.Data.TLERelatedParameters
                )
            )
            if tle_related_parameters_element is not None
            else None
        )

        covariance_matrix_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OMM.Data.CovarianceMatrix)
        )
        covariance_matrix: OMM.Data.CovarianceMatrix | None = (
            OMM.Data.CovarianceMatrix(
                **read_model(covariance_matrix_element, OMM.Data.CovarianceMatrix)
            )
            if covariance_matrix_element is not None
            else None
        )

        user_defined_parameters_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OMM.Data.UserDefinedParameters)
        )
        user_defined_parameters: OMM.Data.UserDefinedParameters | None = (
            OMM.Data.UserDefinedParameters(
                **read_model(
                    user_defined_parameters_element, OMM.Data.UserDefinedParameters
                )
            )
            if user_defined_parameters_element is not None
            else None
        )

        data: OMM.Data = OMM.Data(
            mean_keplerian_elements=mean_keplerian,
            spacecraft_parameters=spacecraft,
            tle_related_parameters=tle_related_parameters,
            covariance_matrix=covariance_matrix,
            user_defined=user_defined_parameters,
        )
        return OMM(
            header=header,
            metadata=metadata,
            data=data,
        )

    def read(
        self,
        path: Path,
    ) -> OMM:
        """
        Read an OMM/XML file and return a validated ``OMM`` domain model.

        Args:
            path (Path): The path to the OMM/XML file.

        Returns:
            OMM: Fully validated ``OMM`` domain model.
        """
        return self._parse(parse_xml_file(path))

    def read_string(
        self,
        content: str,
    ) -> OMM:
        """
        Read an OMM/XML string and return a validated ``OMM`` domain model.

        Args:
            content (str): The OMM/XML string to read.

        Returns:
            OMM: Fully validated ``OMM`` domain model.
        """
        return self._parse(parse_xml_string(content))


OrbitMeanElementsMessageXMLReader = XMLOMMReader
