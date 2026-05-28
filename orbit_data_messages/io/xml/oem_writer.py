"""
XML adapter: Orbit Ephemeris Message writer.

Produces OEM/XML per §8.10.
§8.10.13 — one <stateVector> per ephemeris data line.
§8.10.19 — one <covarianceMatrix> per covariance epoch.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from orbit_data_messages.io.xml._utils import write_model
from orbit_data_messages.models.oem import OEM

_XMLNS_XSI    = "http://www.w3.org/2001/XMLSchema-instance"
_STATE_VECTOR = "stateVector"
_COV_MATRIX   = "covarianceMatrix"


class XMLOEMWriter:
    """
    Writes a validated OEM domain model to an OEM/XML file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OEM, path: Path) -> None:
        root = ET.Element("oem")
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("id", "CCSDS_OEM_VERS")
        root.set("version", message.header.ccsds_oem_vers)

        header_el = ET.SubElement(root, "header")
        write_model(message.header, header_el, skip_fields=frozenset({"ccsds_oem_vers"}))

        body_el = ET.SubElement(root, "body")

        for segment in message.segments:
            segment_el  = ET.SubElement(body_el, "segment")
            metadata_el = ET.SubElement(segment_el, "metadata")
            write_model(segment.metadata, metadata_el)

            data_el = ET.SubElement(segment_el, "data")

            # §7.8.9 — comments at the beginning of the ephemeris data section.
            ed = segment.ephemeris_data
            if ed.comment:
                for c in ed.comment:
                    ET.SubElement(data_el, "COMMENT").text = c

            # §8.10.13 — one <stateVector> per ephemeris data line.
            for sv_line in ed.ephemeris_data_lines:
                sv_el = ET.SubElement(data_el, _STATE_VECTOR)
                write_model(sv_line, sv_el)

            # §8.10.19 — one <covarianceMatrix> per covariance epoch.
            if segment.covariance_matrix is not None:
                cm = segment.covariance_matrix
                # §7.8.9 — comments at the beginning of the covariance section.
                if cm.comment:
                    for c in cm.comment:
                        ET.SubElement(data_el, "COMMENT").text = c
                for cml in cm.covariance_matrix_lines:
                    cov_el = ET.SubElement(data_el, _COV_MATRIX)
                    write_model(cml, cov_el)

        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="unicode", xml_declaration=True)


OrbitEphemerisMessageXMLWriter = XMLOEMWriter
