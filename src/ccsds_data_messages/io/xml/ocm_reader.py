"""
XML adapter: Orbit Comprehensive Message reader.

OCM/XML structure (section 8.11, table 8-9):

  <ocm id="CCSDS_OCM_VERS" version="3.0">
    <header> ... </header>
    <body>
      <segment>
        <metadata> ... </metadata>
        <data>
          <traj>*                   (trajectory, section 8.11.14)
            <TRAJ_TYPE>...</TRAJ_TYPE>
            ...
            <trajLine>100.0 6778.0 ...</trajLine>  (section 8.11.15, xsd:string)
          </traj>
          <phys>?                   (physical properties)
          <cov>*                    (covariance)
            <covLine>...</covLine>
          </cov>
          <man>*                    (maneuver)
            <manLine>...</manLine>
          </man>
          <pert>?                   (perturbations)
          <od>?                     (orbit determination)
          <user>?                   (user-defined)
        </data>
      </segment>
    </body>
  </ocm>

section 8.11.15: <trajLine>, <covLine>, <manLine> elements hold raw data strings
    (xsd:string) that are passed through as ``list[str]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io._ocm_maneuver import parse_maneuver_rows
from ccsds_data_messages.io.xml._utils import _TAG_BODY
from ccsds_data_messages.io.xml._utils import _TAG_DATA
from ccsds_data_messages.io.xml._utils import _TAG_SEGMENT
from ccsds_data_messages.io.xml._utils import get_xml_line_tag
from ccsds_data_messages.io.xml._utils import get_xml_tag
from ccsds_data_messages.io.xml._utils import read_model
from ccsds_data_messages.io.xml.parser import find_all
from ccsds_data_messages.io.xml.parser import find_child
from ccsds_data_messages.io.xml.parser import get_text
from ccsds_data_messages.io.xml.parser import parse_xml_file
from ccsds_data_messages.io.xml.parser import parse_xml_string
from ccsds_data_messages.models.ocm import OCM

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET
    from pathlib import Path

    from pydantic import BaseModel


def _read_block_with_lines(
    element: ET.Element,
    model_class: type[BaseModel],
) -> dict[str, Any]:
    """
    Read keyword elements and raw data lines from an OCM XML block element.

    Args:
        element (ET.Element): The XML element representing the block (e.g. ``<traj>``).
        model_class (type[BaseModel]): The target Pydantic model class. Must declare
            ``_xml_line_tag`` so the data-line child tag is derived automatically.

    Returns:
        dict[str, Any]: Constructor kwargs with ``'data_lines'`` populated from
        the raw line element texts (section 8.11.15).
    """
    kwargs = read_model(element, model_class)
    # Section 8.11.15: data line elements hold raw strings verbatim.
    raw_lines: list[str] = [
        get_text(line_element)
        for line_element in find_all(element, get_xml_line_tag(model_class))
    ]
    # Maneuver rows are typed (parsed by MAN_COMPOSITION); trajectory/covariance
    # rows stay raw strings (registry-driven column schema).
    if model_class is OCM.ManeuverSpecification:
        if (composition := kwargs.get("man_composition")) is None:
            raise ParseError("OCM/XML: <man> block is missing MAN_COMPOSITION.")
        kwargs["data_lines"] = parse_maneuver_rows(composition, raw_lines)
    else:
        kwargs["data_lines"] = raw_lines
    return kwargs


class XMLOCMReader:
    """
    Read an OCM/XML file and return a validated OCM domain model.

    Satisfies ``MessageReaderPort`` structurally.
    """

    def _parse(
        self,
        root: ET.Element,
    ) -> OCM:
        version: str = root.attrib.get("version", "3.0")

        header_element: ET.Element | None = find_child(root, get_xml_tag(OCM.Header))
        segment_element: ET.Element | None = find_child(
            find_child(root, _TAG_BODY), _TAG_SEGMENT
        )
        metadata_element: ET.Element | None = find_child(
            segment_element, get_xml_tag(OCM.Metadata)
        )
        data_element: ET.Element | None = find_child(segment_element, _TAG_DATA)

        header: OCM.Header = OCM.Header(
            **read_model(
                header_element,
                OCM.Header,
                extra_kvs={"CCSDS_OCM_VERS": version},
            )
        )
        metadata: OCM.Metadata = OCM.Metadata(
            **read_model(metadata_element, OCM.Metadata)
        )

        trajectory_states: list[OCM.TrajectoryStateTimeHistory] | None = [
            OCM.TrajectoryStateTimeHistory(
                **_read_block_with_lines(element, OCM.TrajectoryStateTimeHistory)
            )
            for element in find_all(
                data_element, get_xml_tag(OCM.TrajectoryStateTimeHistory)
            )
        ] or None

        phys_element = find_child(
            data_element, get_xml_tag(OCM.SpaceObjectPhysicalCharacteristics)
        )
        physical_characteristics: OCM.SpaceObjectPhysicalCharacteristics | None = (
            OCM.SpaceObjectPhysicalCharacteristics(
                **read_model(phys_element, OCM.SpaceObjectPhysicalCharacteristics)
            )
            if phys_element is not None
            else None
        )

        covariances: list[OCM.CovarianceTimeHistory] | None = [
            OCM.CovarianceTimeHistory(
                **_read_block_with_lines(element, OCM.CovarianceTimeHistory)
            )
            for element in find_all(data_element, get_xml_tag(OCM.CovarianceTimeHistory))
        ] or None

        maneuvers: list[OCM.ManeuverSpecification] | None = [
            OCM.ManeuverSpecification(
                **_read_block_with_lines(element, OCM.ManeuverSpecification)
            )
            for element in find_all(data_element, get_xml_tag(OCM.ManeuverSpecification))
        ] or None

        pert_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OCM.PerturbationsSpecification)
        )
        perturbations: OCM.PerturbationsSpecification | None = (
            OCM.PerturbationsSpecification(
                **read_model(pert_element, OCM.PerturbationsSpecification)
            )
            if pert_element is not None
            else None
        )

        od_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OCM.OrbitDeterminationData)
        )
        orbit_determination: OCM.OrbitDeterminationData | None = (
            OCM.OrbitDeterminationData(
                **read_model(od_element, OCM.OrbitDeterminationData)
            )
            if od_element is not None
            else None
        )

        user_element: ET.Element | None = find_child(
            data_element, get_xml_tag(OCM.UserDefinedParameters)
        )
        user_defined: OCM.UserDefinedParameters | None = (
            OCM.UserDefinedParameters(
                **read_model(user_element, OCM.UserDefinedParameters)
            )
            if user_element is not None
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
        Read an OCM/XML file and return a validated ``OCM`` domain model.

        Args:
            path (Path): The path to the XML OCM file.

        Returns:
            OCM: Validated OCM domain model.
        """
        return self._parse(parse_xml_file(path))

    def read_string(
        self,
        content: str,
    ) -> OCM:
        """
        Read an OCM/XML string and return a validated OCM domain model.

        Args:
            content (str): The OCM/XML string to read.

        Returns:
            OCM: Validated OCM domain model.
        """
        return self._parse(parse_xml_string(content))


OrbitComprehensiveMessageXMLReader = XMLOCMReader
