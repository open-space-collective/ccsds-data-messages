"""
XML adapter: Orbit Parameter Message reader.

OPM/XML structure (§8.8, table 8-3, Annex G fig G-5):

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

§8.1   — ODM keyword elements use all-caps names (same as KVN keywords).
§8.3.6 — version number is the root 'version' attribute, not a child element.
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io._utils import build_keyword_map
from orbit_data_messages.io.xml._utils import read_model
from orbit_data_messages.io.xml.parser import find_all
from orbit_data_messages.io.xml.parser import find_child
from orbit_data_messages.io.xml.parser import parse_xml_file
from orbit_data_messages.models.opm import OPM

# §8.8.14, table 8-3 — OPM/XML logical block tag names.
_STATE_VECTOR    = "stateVector"
_KEPLERIAN       = "keplerianElements"
_SPACECRAFT      = "spacecraftParameters"
_COV_MATRIX      = "covarianceMatrix"
_MANEUVER        = "maneuverParameters"
_USER_DEFINED    = "userDefinedParameters"

# Field name for the version keyword — read from FieldMetadata, not hardcoded.
_VERSION_FIELD = build_keyword_map(OPM.Header).get("CCSDS_OPM_VERS")


class XMLOPMReader:
    """
    Reads an OPM/XML file and returns a validated OPM domain model.

    Satisfies MessageReaderPort structurally.
    """

    def read(self, path: Path) -> OPM:
        """Reads an XML OPM file and returns a validated OPM domain model.

        Args:
            path: Path to the XML OPM file.

        Returns:
            A fully validated OPM domain model. Pydantic ValidationError is
            never swallowed — it propagates to the caller unchanged.
        """
        root = parse_xml_file(path)

        # §8.3.6 — version is the root 'version' attribute.
        version = root.attrib.get("version", "3.0")

        header_el   = find_child(root, "header")
        segment_el  = find_child(find_child(root, "body"), "segment")
        metadata_el = find_child(segment_el, "metadata")
        data_el     = find_child(segment_el, "data")

        header = OPM.Header(**read_model(
            header_el, OPM.Header,
            extra_kvs={"CCSDS_OPM_VERS": version},
        ))
        metadata = OPM.Metadata(**read_model(metadata_el, OPM.Metadata))

        sv_el = find_child(data_el, _STATE_VECTOR)
        state_vector = OPM.Data.StateVector(**read_model(sv_el, OPM.Data.StateVector))

        ke_el = find_child(data_el, _KEPLERIAN)
        keplerian = (
            OPM.Data.OsculatingKeplerianElements(
                **read_model(ke_el, OPM.Data.OsculatingKeplerianElements)
            )
            if ke_el is not None else None
        )

        sp_el = find_child(data_el, _SPACECRAFT)
        spacecraft = (
            OPM.Data.SpacecraftParameters(**read_model(sp_el, OPM.Data.SpacecraftParameters))
            if sp_el is not None else None
        )

        cov_el = find_child(data_el, _COV_MATRIX)
        cov = (
            OPM.Data.CovarianceMatrix(**read_model(cov_el, OPM.Data.CovarianceMatrix))
            if cov_el is not None else None
        )

        man_els = find_all(data_el, _MANEUVER)
        maneuvers = (
            [OPM.Data.ManeuverParameters(**read_model(el, OPM.Data.ManeuverParameters))
             for el in man_els]
            or None
        )

        user_el = find_child(data_el, _USER_DEFINED)
        user = (
            OPM.Data.UserDefinedParameters(**read_model(user_el, OPM.Data.UserDefinedParameters))
            if user_el is not None else None
        )

        data = OPM.Data(
            state_vector=state_vector,
            osculating_keplerian_elements=keplerian,
            spacecraft_parameters=spacecraft,
            covariance_matrix=cov,
            maneuvers=maneuvers,
            user_defined=user,
        )
        return OPM(header=header, metadata=metadata, data=data)


OrbitParameterMessageXMLReader = XMLOPMReader
