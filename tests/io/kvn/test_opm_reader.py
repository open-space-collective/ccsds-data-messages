"""
Unit tests for the KVN OPM reader adapter.

Instantiates ``KVNOPMReader`` directly (as opposed to the high-level
``read()`` dispatch tested in ``tests/io/test_reader.py``) and exercises
``read()`` / ``read_string()`` against the OPM KVN spec fixtures.

Module under test:
  src/ccsds_data_messages/io/kvn/opm_reader.py
"""

from __future__ import annotations

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OPM
from ccsds_data_messages.io.kvn.opm_reader import KVNOPMReader

_KVN_FIXTURES: list[str] = [
    "opm_g1_simple.kvn",
    "opm_g2_maneuvers.kvn",
    "opm_g3_covariance.kvn",
    "opm_g4_keplerian_covariance.kvn",
]


class TestKVNOPMReader:
    def test_read_returns_opm_instance(self):
        reader = KVNOPMReader()
        msg = reader.read(FIXTURES / "opm_g1_simple.kvn")
        assert isinstance(msg, OPM)

    def test_read_populates_stable_fields(self):
        reader = KVNOPMReader()
        msg = reader.read(FIXTURES / "opm_g1_simple.kvn")
        assert msg.header.originator == "JAXA"
        assert msg.metadata.object_name == "OSPREY 5"
        assert msg.data.state_vector.x == pytest.approx(6503.514)

    @pytest.mark.parametrize("fixture", _KVN_FIXTURES)
    def test_read_all_fixtures_return_opm(self, fixture: str):
        reader = KVNOPMReader()
        msg = reader.read(FIXTURES / fixture)
        assert isinstance(msg, OPM)

    @pytest.mark.parametrize("fixture", _KVN_FIXTURES)
    def test_read_string_matches_read(self, fixture: str):
        reader = KVNOPMReader()
        path = FIXTURES / fixture
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OPM)
        assert from_string.header.originator == from_path.header.originator
        assert from_string.metadata.object_name == from_path.metadata.object_name
        assert from_string.data.state_vector.x == pytest.approx(
            from_path.data.state_vector.x
        )
        assert from_string.model_dump() == from_path.model_dump()
