"""
XML adapter: Orbit Parameter Message writer.

Produces OPM/XML per §8.8, table 8-3, Annex G fig G-5.
Keyword element names come from FieldMetadata — nothing hardcoded.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from orbit_data_messages.io.xml._utils import write_model
from orbit_data_messages.models.opm import OPM

_XMLNS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# §8.8.14, table 8-3 — OPM/XML logical block tag names.
_STATE_VECTOR = "stateVector"
_KEPLERIAN    = "keplerianElements"
_SPACECRAFT   = "spacecraftParameters"
_COV_MATRIX   = "covarianceMatrix"
_MANEUVER     = "maneuverParameters"
_USER_DEFINED = "userDefinedParameters"


class XMLOPMWriter:
    """
    Writes a validated OPM domain model to an OPM/XML file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OPM, path: Path) -> None:
        # §8.8.1–8.8.4 — root element with required attributes.
        root = ET.Element("opm")
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("id", "CCSDS_OPM_VERS")
        # §8.3.6 — version number comes from the domain model field.
        root.set("version", message.header.ccsds_opm_vers)

        # §8.4 — <header> element; skip ccsds_opm_vers (goes to root attr).
        header_el = ET.SubElement(root, "header")
        write_model(message.header, header_el, skip_fields=frozenset({"ccsds_opm_vers"}))

        body_el    = ET.SubElement(root, "body")
        segment_el = ET.SubElement(body_el, "segment")
        meta_el    = ET.SubElement(segment_el, "metadata")
        write_model(message.metadata, meta_el)

        data_el = ET.SubElement(segment_el, "data")

        # State vector — mandatory.
        sv_el = ET.SubElement(data_el, _STATE_VECTOR)
        write_model(message.data.state_vector, sv_el)

        if message.data.osculating_keplerian_elements is not None:
            ke_el = ET.SubElement(data_el, _KEPLERIAN)
            write_model(message.data.osculating_keplerian_elements, ke_el)

        if message.data.spacecraft_parameters is not None:
            sp_el = ET.SubElement(data_el, _SPACECRAFT)
            write_model(message.data.spacecraft_parameters, sp_el)

        if message.data.covariance_matrix is not None:
            cov_el = ET.SubElement(data_el, _COV_MATRIX)
            write_model(message.data.covariance_matrix, cov_el)

        if message.data.maneuvers:
            for man in message.data.maneuvers:
                man_el = ET.SubElement(data_el, _MANEUVER)
                write_model(man, man_el)

        if message.data.user_defined is not None:
            user_el = ET.SubElement(data_el, _USER_DEFINED)
            write_model(message.data.user_defined, user_el)

        ET.indent(root, space="  ")
        tree = ET.ElementTree(root)
        tree.write(path, encoding="unicode", xml_declaration=True)


OrbitParameterMessageXMLWriter = XMLOPMWriter
