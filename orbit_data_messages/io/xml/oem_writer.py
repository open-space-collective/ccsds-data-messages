"""
XML adapter: Orbit Ephemeris Message writer.

Produces OEM/XML per §8.10.
§8.10.13 — one <stateVector> per ephemeris data line.
§8.10.19 — one <covarianceMatrix> per covariance epoch.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.io.xml._utils import write_model
from orbit_data_messages.models.oem import OEM

_XMLNS_XSI    = "http://www.w3.org/2001/XMLSchema-instance"
_NDM_SCHEMA   = "https://sanaregistry.org/r/ndmxml_unqualified/ndmxml-3.0.0-master-3.0.xsd"
_STATE_VECTOR = "stateVector"
_COV_MATRIX   = "covarianceMatrix"


class XMLOEMWriter:
    """
    Writes a validated OEM domain model to an OEM/XML file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OEM, path: Path, *, options: WriterOptions | None = None) -> None:
        """Serializes a validated OEM domain model to an XML file at path.

        Args:
            message: Validated OEM instance to serialize.
            path: Destination file. Created or overwritten.
            options: Formatting options. When omitted, WriterOptions() defaults apply.
        """
        root = ET.Element("oem")
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("xsi:noNamespaceSchemaLocation", _NDM_SCHEMA)
        root.set("id", "CCSDS_OEM_VERS")
        root.set("version", message.header.ccsds_oem_vers)

        header_el = ET.SubElement(root, "header")
        write_model(message.header, header_el, skip_fields=frozenset({"ccsds_oem_vers"}), options=options)

        body_el = ET.SubElement(root, "body")

        for segment in message.segments:
            segment_el  = ET.SubElement(body_el, "segment")
            metadata_el = ET.SubElement(segment_el, "metadata")
            write_model(segment.metadata, metadata_el, options=options)

            data_el = ET.SubElement(segment_el, "data")

            # §7.8.9 — comments at the beginning of the ephemeris data section.
            ed = segment.ephemeris_data
            if ed.comment:
                for c in ed.comment:
                    ET.SubElement(data_el, "COMMENT").text = c

            # §8.10.13 — one <stateVector> per ephemeris data line.
            for sv_line in ed.ephemeris_data_lines:
                sv_el = ET.SubElement(data_el, _STATE_VECTOR)
                write_model(sv_line, sv_el, options=options)

            # §8.10.19 — one <covarianceMatrix> per covariance epoch.
            if segment.covariance_matrix is not None:
                cm = segment.covariance_matrix
                # §7.8.9 — comments at the beginning of the covariance section.
                if cm.comment:
                    for c in cm.comment:
                        ET.SubElement(data_el, "COMMENT").text = c
                for cml in cm.covariance_matrix_lines:
                    cov_el = ET.SubElement(data_el, _COV_MATRIX)
                    write_model(cml, cov_el, options=options)

        ET.indent(root, space="  ")
        # Write XML declaration manually to use double quotes and uppercase UTF-8
        # (ElementTree always emits single quotes / lowercase, which differs from
        # the CCSDS reference format).
        xml_body = ET.tostring(root, encoding="unicode")
        path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body,
            encoding="utf-8",
        )


OrbitEphemerisMessageXMLWriter = XMLOEMWriter
