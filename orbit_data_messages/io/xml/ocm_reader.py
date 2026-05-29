"""
XML adapter: Orbit Comprehensive Message reader.

OCM/XML structure (§8.11, table 8-9):

  <ocm id="CCSDS_OCM_VERS" version="3.0">
    <header> ... </header>
    <body>
      <segment>
        <metadata> ... </metadata>
        <data>
          <traj>*                   (trajectory, §8.11.14)
            <TRAJ_TYPE>...</TRAJ_TYPE>
            ...
            <trajLine>100.0 6778.0 ...</trajLine>  (§8.11.15, xsd:string)
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

§8.11.15 — <trajLine>, <covLine>, <manLine> elements hold raw data strings
           (xsd:string) that are passed through as list[str].
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.xml._utils import read_model
from orbit_data_messages.io.xml.parser import find_all
from orbit_data_messages.io.xml.parser import find_child
from orbit_data_messages.io.xml.parser import get_text
from orbit_data_messages.io.xml.parser import parse_xml_file
from orbit_data_messages.models.ocm import OCM

# §8.11, table 8-9 — OCM/XML section tags and data-line tags.
_TRAJ  = "traj";   _TRAJ_LINE  = "trajLine"
_PHYS  = "phys"
_COV   = "cov";    _COV_LINE   = "covLine"
_MAN   = "man";    _MAN_LINE   = "manLine"
_PERT  = "pert"
_OD    = "od"
_USER  = "user"


def _read_block_with_lines(el, model_class, line_tag: str):
    """Read keyword elements + raw data lines from an OCM block element."""
    kwargs = read_model(el, model_class)
    # §8.11.15 — data line elements hold raw strings verbatim.
    kwargs["data_lines"] = [get_text(line_el) for line_el in find_all(el, line_tag)]
    return kwargs


class XMLOCMReader:
    """
    Reads an OCM/XML file and returns a validated OCM domain model.

    Satisfies MessageReaderPort structurally.
    """

    def read(self, path: Path) -> OCM:
        """Reads an XML OCM file and returns a validated OCM domain model.

        Args:
            path: Path to the XML OCM file.

        Returns:
            A fully validated OCM domain model. Pydantic ValidationError is
            never swallowed — it propagates to the caller unchanged.
        """
        root = parse_xml_file(path)
        version = root.attrib.get("version", "3.0")

        header_el   = find_child(root, "header")
        segment_el  = find_child(find_child(root, "body"), "segment")
        metadata_el = find_child(segment_el, "metadata")
        data_el     = find_child(segment_el, "data")

        header = OCM.Header(**read_model(
            header_el, OCM.Header,
            extra_kvs={"CCSDS_OCM_VERS": version},
        ))
        metadata = OCM.Metadata(**read_model(metadata_el, OCM.Metadata))

        trajectory_states = (
            [OCM.TrajectoryStateBlock(**_read_block_with_lines(el, OCM.TrajectoryStateBlock, _TRAJ_LINE))
             for el in find_all(data_el, _TRAJ)]
            or None
        )

        phys_el = find_child(data_el, _PHYS)
        physical_properties = (
            OCM.PhysicalPropertiesBlock(**read_model(phys_el, OCM.PhysicalPropertiesBlock))
            if phys_el is not None else None
        )

        covariances = (
            [OCM.CovarianceBlock(**_read_block_with_lines(el, OCM.CovarianceBlock, _COV_LINE))
             for el in find_all(data_el, _COV)]
            or None
        )

        maneuvers = (
            [OCM.ManeuverBlock(**_read_block_with_lines(el, OCM.ManeuverBlock, _MAN_LINE))
             for el in find_all(data_el, _MAN)]
            or None
        )

        pert_el = find_child(data_el, _PERT)
        perturbations = (
            OCM.PerturbationsBlock(**read_model(pert_el, OCM.PerturbationsBlock))
            if pert_el is not None else None
        )

        od_el = find_child(data_el, _OD)
        orbit_determination = (
            OCM.OrbitDeterminationBlock(**read_model(od_el, OCM.OrbitDeterminationBlock))
            if od_el is not None else None
        )

        user_el = find_child(data_el, _USER)
        user_defined = (
            OCM.UserDefinedParameters(**read_model(user_el, OCM.UserDefinedParameters))
            if user_el is not None else None
        )

        return OCM(
            header=header,
            metadata=metadata,
            trajectory_states=trajectory_states,
            physical_properties=physical_properties,
            covariances=covariances,
            maneuvers=maneuvers,
            perturbations=perturbations,
            orbit_determination=orbit_determination,
            user_defined=user_defined,
        )


OrbitComprehensiveMessageXMLReader = XMLOCMReader
