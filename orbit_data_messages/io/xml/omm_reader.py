"""
XML adapter: Orbit Mean-Elements Message reader.

OMM/XML structure (§8.9, table 8-5):

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

§8.1   — ODM keyword elements use all-caps names.
§8.3.6 — version number is the root 'version' attribute.
§4.2.4.8 — maneuvers not accommodated in OMM.
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.xml._utils import read_model
from orbit_data_messages.io.xml.parser import find_child
from orbit_data_messages.io.xml.parser import parse_xml_file
from orbit_data_messages.models.omm import OMM

# §8.9, table 8-5 — OMM/XML logical block tag names.
_MEAN_ELEMENTS = "meanElements"
_SPACECRAFT    = "spacecraftParameters"
_TLE_PARAMS    = "tleParameters"
_COV_MATRIX    = "covarianceMatrix"
_USER_DEFINED  = "userDefinedParameters"


class XMLOMMReader:
    """
    Reads an OMM/XML file and returns a validated OMM domain model.

    Satisfies MessageReaderPort structurally.
    """

    def read(self, path: Path) -> OMM:
        root = parse_xml_file(path)
        version = root.attrib.get("version", "3.0")

        header_el   = find_child(root, "header")
        segment_el  = find_child(find_child(root, "body"), "segment")
        metadata_el = find_child(segment_el, "metadata")
        data_el     = find_child(segment_el, "data")

        header = OMM.Header(**read_model(
            header_el, OMM.Header,
            extra_kvs={"CCSDS_OMM_VERS": version},
        ))
        metadata = OMM.Metadata(**read_model(metadata_el, OMM.Metadata))

        me_el = find_child(data_el, _MEAN_ELEMENTS)
        mean_keplerian = OMM.Data.MeanKeplerianElements(
            **read_model(me_el, OMM.Data.MeanKeplerianElements)
        )

        sp_el = find_child(data_el, _SPACECRAFT)
        spacecraft = (
            OMM.Data.SpacecraftParameters(**read_model(sp_el, OMM.Data.SpacecraftParameters))
            if sp_el is not None else None
        )

        tle_el = find_child(data_el, _TLE_PARAMS)
        tle_params = (
            OMM.Data.TLERelatedParameters(**read_model(tle_el, OMM.Data.TLERelatedParameters))
            if tle_el is not None else None
        )

        cov_el = find_child(data_el, _COV_MATRIX)
        cov = (
            OMM.Data.CovarianceMatrix(**read_model(cov_el, OMM.Data.CovarianceMatrix))
            if cov_el is not None else None
        )

        user_el = find_child(data_el, _USER_DEFINED)
        user = (
            OMM.Data.UserDefinedParameters(**read_model(user_el, OMM.Data.UserDefinedParameters))
            if user_el is not None else None
        )

        data = OMM.Data(
            mean_keplerian_elements=mean_keplerian,
            spacecraft_parameters=spacecraft,
            tle_related_parameters=tle_params,
            covariance_matrix=cov,
            user_defined=user,
        )
        return OMM(header=header, metadata=metadata, data=data)


OrbitMeanElementsMessageXMLReader = XMLOMMReader
