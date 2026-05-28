"""
XML adapter: Orbit Comprehensive Message writer.

Produces OCM/XML per §8.11, table 8-9.
§8.11.15 — trajLine / covLine / manLine elements hold raw data strings.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from orbit_data_messages.io.xml._utils import write_model
from orbit_data_messages.models.ocm import OCM

_XMLNS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# §8.11, table 8-9 — section and data-line tag names.
_TRAJ = "traj";  _TRAJ_LINE = "trajLine"
_PHYS = "phys"
_COV  = "cov";   _COV_LINE  = "covLine"
_MAN  = "man";   _MAN_LINE  = "manLine"
_PERT = "pert"
_OD   = "od"
_USER = "user"


def _write_block_with_lines(block, data_el, section_tag: str, line_tag: str) -> None:
    """Write keyword elements + raw data line elements for an OCM block."""
    section_el = ET.SubElement(data_el, section_tag)
    write_model(block, section_el)
    # §8.11.15 — each raw data string becomes its own line element.
    for line in block.data_lines:
        line_el = ET.SubElement(section_el, line_tag)
        line_el.text = line


class XMLOCMWriter:
    """
    Writes a validated OCM domain model to an OCM/XML file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OCM, path: Path) -> None:
        root = ET.Element("ocm")
        root.set("xmlns:xsi", _XMLNS_XSI)
        root.set("id", "CCSDS_OCM_VERS")
        root.set("version", message.header.ccsds_ocm_vers)

        header_el = ET.SubElement(root, "header")
        write_model(message.header, header_el, skip_fields=frozenset({"ccsds_ocm_vers"}))

        body_el    = ET.SubElement(root, "body")
        segment_el = ET.SubElement(body_el, "segment")
        meta_el    = ET.SubElement(segment_el, "metadata")
        write_model(message.metadata, meta_el)

        data_el = ET.SubElement(segment_el, "data")

        # §6.2.1.1, table 6-1 — block order is mandatory.
        if message.trajectory_states:
            for block in message.trajectory_states:
                _write_block_with_lines(block, data_el, _TRAJ, _TRAJ_LINE)

        if message.physical_properties is not None:
            phys_el = ET.SubElement(data_el, _PHYS)
            write_model(message.physical_properties, phys_el)

        if message.covariances:
            for block in message.covariances:
                _write_block_with_lines(block, data_el, _COV, _COV_LINE)

        if message.maneuvers:
            for block in message.maneuvers:
                _write_block_with_lines(block, data_el, _MAN, _MAN_LINE)

        if message.perturbations is not None:
            pert_el = ET.SubElement(data_el, _PERT)
            write_model(message.perturbations, pert_el)

        if message.orbit_determination is not None:
            od_el = ET.SubElement(data_el, _OD)
            write_model(message.orbit_determination, od_el)

        if message.user_defined is not None:
            user_el = ET.SubElement(data_el, _USER)
            write_model(message.user_defined, user_el)

        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="unicode", xml_declaration=True)


OrbitComprehensiveMessageXMLWriter = XMLOCMWriter
