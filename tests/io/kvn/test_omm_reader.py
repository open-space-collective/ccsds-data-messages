"""
Unit tests for the KVN OMM reader adapter.

Instantiates KVNOMMReader directly (not the high-level read() dispatch) and
exercises read()/read_string() against the OMM KVN spec fixtures.

Modules under test:
  src/ccsds_data_messages/io/kvn/omm_reader.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OMM
from ccsds_data_messages.io.kvn.omm_reader import KVNOMMReader

if TYPE_CHECKING:
    from pathlib import Path

_REL_TOLERANCE: float = 1e-9


class TestKVNOMMReader:
    def test_read_returns_omm(self):
        reader = KVNOMMReader()
        msg = reader.read(FIXTURES / "omm_g7.kvn")
        assert isinstance(msg, OMM)

    def test_read_parses_stable_fields(self):
        reader = KVNOMMReader()
        msg = reader.read(FIXTURES / "omm_g7.kvn")
        assert msg.header.originator == "NOAA"
        assert msg.metadata.object_name == "GOES 9"
        assert msg.metadata.mean_element_theory == "SGP/SGP4"
        mke = msg.data.mean_keplerian_elements
        assert mke.mean_motion == pytest.approx(1.00273272, rel=_REL_TOLERANCE)
        assert mke.inclination == pytest.approx(3.0539, rel=_REL_TOLERANCE)

    def test_read_string_agrees_with_read(self):
        reader = KVNOMMReader()
        path = FIXTURES / "omm_g7.kvn"
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OMM)
        assert from_path.model_dump() == from_string.model_dump()

    def test_read_covariance_fixture_populates_covariance_block(self):
        reader = KVNOMMReader()
        msg = reader.read(FIXTURES / "omm_g8_covariance.kvn")
        assert msg.data.covariance_matrix is not None
        assert msg.data.covariance_matrix.cx_x == pytest.approx(
            3.331349476038534e-04, rel=_REL_TOLERANCE
        )

    def test_read_units_fixture_populates_user_defined_block(self):
        reader = KVNOMMReader()
        msg = reader.read(FIXTURES / "omm_g9_units.kvn")
        assert msg.data.user_defined is not None
        assert msg.data.user_defined.user_defined["EARTH_MODEL"] == "WGS-84"

    def test_read_string_agrees_with_read_for_all_kvn_fixtures(self):
        reader = KVNOMMReader()
        for name in ("omm_g7.kvn", "omm_g8_covariance.kvn", "omm_g9_units.kvn"):
            path: Path = FIXTURES / name
            from_path = reader.read(path)
            from_string = reader.read_string(path.read_text(encoding="utf-8"))
            assert from_path.model_dump() == from_string.model_dump()
