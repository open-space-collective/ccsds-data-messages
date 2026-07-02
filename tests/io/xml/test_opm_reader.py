"""
Unit tests for the XML OPM reader adapter.

Instantiates ``XMLOPMReader`` directly (as opposed to the high-level
``read()`` dispatch tested in ``tests/io/test_reader.py``) and exercises
``read()`` / ``read_string()`` against the OPM XML spec fixture.

Module under test:
  src/ccsds_data_messages/io/xml/opm_reader.py
"""

from __future__ import annotations

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OPM
from ccsds_data_messages.io.xml.opm_reader import XMLOPMReader

_XML_FIXTURE: str = "opm_g5.xml"


class TestXMLOPMReader:
    def test_read_returns_opm_instance(self):
        reader = XMLOPMReader()
        msg = reader.read(FIXTURES / _XML_FIXTURE)
        assert isinstance(msg, OPM)

    def test_read_populates_stable_fields(self):
        reader = XMLOPMReader()
        msg = reader.read(FIXTURES / _XML_FIXTURE)
        assert msg.header.originator == "JAXA"
        assert msg.metadata.object_name == "OSPREY 5"
        assert msg.data.state_vector.x == pytest.approx(6503.514)

    def test_read_string_matches_read(self):
        reader = XMLOPMReader()
        path = FIXTURES / _XML_FIXTURE
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OPM)
        assert from_string.header.originator == from_path.header.originator
        assert from_string.metadata.object_name == from_path.metadata.object_name
        assert from_string.data.state_vector.x == pytest.approx(
            from_path.data.state_vector.x
        )
        assert from_string.model_dump() == from_path.model_dump()
