"""
Unit tests for the XML OEM reader adapter.

Instantiates ``XMLOEMReader`` directly (as opposed to the high-level
``read()`` dispatch tested in ``tests/io/test_reader.py``) and exercises
``read()`` / ``read_string()`` against the OEM XML spec fixture.

Module under test:
  src/ccsds_data_messages/io/xml/oem_reader.py
"""

from __future__ import annotations

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OEM
from ccsds_data_messages.io.xml.oem_reader import XMLOEMReader


class TestXMLOEMReader:
    def test_read_returns_oem_instance(self):
        reader = XMLOEMReader()
        msg = reader.read(FIXTURES / "oem_g14.xml")
        assert isinstance(msg, OEM)

    def test_read_populates_stable_fields(self):
        reader = XMLOEMReader()
        msg = reader.read(FIXTURES / "oem_g14.xml")
        assert msg.header.originator == "JPL"
        segment = msg.segments[0]
        assert segment.metadata.object_name == "MARS GLOBAL SURVEYOR"
        first_line = segment.ephemeris_data.ephemeris_data_lines[0]
        assert first_line.x == pytest.approx(2789.6)

    def test_read_parses_at_least_one_segment_with_data(self):
        reader = XMLOEMReader()
        msg = reader.read(FIXTURES / "oem_g14.xml")
        assert len(msg.segments) >= 1
        assert len(msg.segments[0].ephemeris_data.ephemeris_data_lines) >= 1

    def test_read_string_matches_read(self):
        reader = XMLOEMReader()
        path = FIXTURES / "oem_g14.xml"
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OEM)
        assert from_string.header.originator == from_path.header.originator
        assert (
            from_string.segments[0].metadata.object_name
            == from_path.segments[0].metadata.object_name
        )
        assert from_string.model_dump() == from_path.model_dump()
