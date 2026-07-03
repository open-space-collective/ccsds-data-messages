"""
Unit tests for the XML OMM reader adapter.

Instantiates XMLOMMReader directly (not the high-level read() dispatch) and
exercises read()/read_string() against the OMM XML spec fixture.

Modules under test:
  src/ccsds_data_messages/io/xml/omm_reader.py
"""

from __future__ import annotations

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OMM
from ccsds_data_messages.io.xml.omm_reader import XMLOMMReader

_REL_TOLERANCE: float = 1e-9


class TestXMLOMMReader:
    def test_read_returns_omm(self):
        reader = XMLOMMReader()
        msg = reader.read(FIXTURES / "omm_g10.xml")
        assert isinstance(msg, OMM)

    def test_read_parses_stable_fields(self):
        reader = XMLOMMReader()
        msg = reader.read(FIXTURES / "omm_g10.xml")
        assert msg.header.originator == "NOAA"
        assert msg.metadata.object_name == "GOES-9"
        assert msg.metadata.mean_element_theory == "SGP4"
        mke = msg.data.mean_keplerian_elements
        assert mke.mean_motion == pytest.approx(1.00273272, rel=_REL_TOLERANCE)
        assert mke.eccentricity == pytest.approx(0.0005013, rel=_REL_TOLERANCE)

    def test_read_parses_covariance_block(self):
        reader = XMLOMMReader()
        msg = reader.read(FIXTURES / "omm_g10.xml")
        assert msg.data.covariance_matrix is not None
        assert msg.data.covariance_matrix.cx_x == pytest.approx(
            3.331349476038534e-04, rel=_REL_TOLERANCE
        )

    def test_read_string_agrees_with_read(self):
        reader = XMLOMMReader()
        path = FIXTURES / "omm_g10.xml"
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OMM)
        assert from_path.model_dump() == from_string.model_dump()
