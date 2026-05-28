"""
XML adapter: Orbit Mean-Elements Message writer.

Produces OMM/XML per §8.9, table 8-5.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from orbit_data_messages.io.xml._utils import write_model
from orbit_data_messages.models.omm import OMM

_XMLNS_XSI     = "http://www.w3.org/2001/XMLSchema-instance"
_MEAN_ELEMENTS = "meanElements"
_SPACECRAFT    = "spacecraftParameters"
_TLE_PARAMS    = "tleParameters"
_COV_MATRIX    = "covarianceMatrix"
_USER_DEFINED  = "userDefinedParameters"


class XMLOMMWriter:
    """
    Writes a validated OMM domain model to an OMM/XML file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OMM, path: Path) -> None:
        root = ET.Element("omm")
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("id", "CCSDS_OMM_VERS")
        root.set("version", message.header.ccsds_omm_vers)

        header_el = ET.SubElement(root, "header")
        write_model(message.header, header_el, skip_fields=frozenset({"ccsds_omm_vers"}))

        body_el    = ET.SubElement(root, "body")
        segment_el = ET.SubElement(body_el, "segment")
        meta_el    = ET.SubElement(segment_el, "metadata")
        write_model(message.metadata, meta_el)

        data_el = ET.SubElement(segment_el, "data")

        me_el = ET.SubElement(data_el, _MEAN_ELEMENTS)
        write_model(message.data.mean_keplerian_elements, me_el)

        if message.data.spacecraft_parameters is not None:
            sp_el = ET.SubElement(data_el, _SPACECRAFT)
            write_model(message.data.spacecraft_parameters, sp_el)

        if message.data.tle_related_parameters is not None:
            tle_el = ET.SubElement(data_el, _TLE_PARAMS)
            write_model(message.data.tle_related_parameters, tle_el)

        if message.data.covariance_matrix is not None:
            cov_el = ET.SubElement(data_el, _COV_MATRIX)
            write_model(message.data.covariance_matrix, cov_el)

        if message.data.user_defined is not None:
            user_el = ET.SubElement(data_el, _USER_DEFINED)
            write_model(message.data.user_defined, user_el)

        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="unicode", xml_declaration=True)


OrbitMeanElementsMessageXMLWriter = XMLOMMWriter
