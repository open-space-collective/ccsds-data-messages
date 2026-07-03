"""
Unit tests for the KVN OEM reader adapter.

Instantiates ``KVNOEMReader`` directly (as opposed to the high-level
``read()`` dispatch tested in ``tests/io/test_reader.py``) and exercises
``read()`` / ``read_string()`` against the OEM KVN spec fixtures.

Module under test:
  src/ccsds_data_messages/io/kvn/oem_reader.py
"""

from __future__ import annotations

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OEM
from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io.kvn.oem_reader import KVNOEMReader

_KVN_FIXTURES: list[str] = [
    "oem_g11.kvn",
    "oem_g12_accelerations.kvn",
    "oem_g13_covariance.kvn",
]


class TestKVNOEMReader:
    def test_read_returns_oem_instance(self):
        reader = KVNOEMReader()
        msg = reader.read(FIXTURES / "oem_g11.kvn")
        assert isinstance(msg, OEM)

    def test_read_populates_stable_fields(self):
        reader = KVNOEMReader()
        msg = reader.read(FIXTURES / "oem_g11.kvn")
        assert msg.header.originator == "JPL"
        segment = msg.segments[0]
        assert segment.metadata.object_name == "MARS GLOBAL SURVEYOR"
        first_line = segment.ephemeris_data.ephemeris_data_lines[0]
        assert first_line.x == pytest.approx(2789.619)

    def test_read_parses_multiple_segments(self):
        """oem_g11.kvn declares two META_START/META_STOP segments."""
        reader = KVNOEMReader()
        msg = reader.read(FIXTURES / "oem_g11.kvn")
        assert len(msg.segments) == 2
        for segment in msg.segments:
            assert len(segment.ephemeris_data.ephemeris_data_lines) >= 1

    def test_read_parses_accelerations(self):
        """oem_g12 ephemeris lines carry 10 tokens (position, velocity, accel)."""
        reader = KVNOEMReader()
        msg = reader.read(FIXTURES / "oem_g12_accelerations.kvn")
        first_line = msg.segments[0].ephemeris_data.ephemeris_data_lines[0]
        assert first_line.x_ddot is not None
        assert first_line.x_ddot == pytest.approx(0.008)

    def test_read_parses_covariance_block(self):
        """oem_g13 carries a COVARIANCE_START/COVARIANCE_STOP block."""
        reader = KVNOEMReader()
        msg = reader.read(FIXTURES / "oem_g13_covariance.kvn")
        covariance = msg.segments[0].covariance_matrix
        assert covariance is not None
        assert len(covariance.covariance_matrix_lines) >= 1

    @pytest.mark.parametrize("fixture", _KVN_FIXTURES)
    def test_read_all_fixtures_return_oem(self, fixture: str):
        reader = KVNOEMReader()
        msg = reader.read(FIXTURES / fixture)
        assert isinstance(msg, OEM)

    @pytest.mark.parametrize("fixture", _KVN_FIXTURES)
    def test_read_string_matches_read(self, fixture: str):
        reader = KVNOEMReader()
        path = FIXTURES / fixture
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OEM)
        assert from_string.header.originator == from_path.header.originator
        assert (
            from_string.segments[0].metadata.object_name
            == from_path.segments[0].metadata.object_name
        )
        assert from_string.model_dump() == from_path.model_dump()


class TestKVNOEMReaderMalformed:
    """
    Malformed content must surface as ParseError, never a bare ValueError.

    ``read()``/``read_string()`` only translate ``pydantic.ValidationError``; any
    other exception escapes as-is. These guard the failure contract documented in
    the public ``read``/``read_string`` docstrings.
    """

    def test_wrong_token_count_raises_parse_error(self):
        text = (FIXTURES / "oem_g11.kvn").read_text(encoding="utf-8")
        # 6 state components + epoch = 7 tokens; add an 8th to break the count.
        malformed = text.replace(
            "4.73372 -2.49586 -1.04195",
            "4.73372 -2.49586 -1.04195 0.0",
        )
        assert malformed != text
        with pytest.raises(ParseError):
            KVNOEMReader().read_string(malformed)

    def test_non_numeric_ephemeris_value_raises_parse_error(self):
        text = (FIXTURES / "oem_g11.kvn").read_text(encoding="utf-8")
        malformed = text.replace("2789.619", "NOTANUMBER")
        assert malformed != text
        with pytest.raises(ParseError):
            KVNOEMReader().read_string(malformed)

    def test_non_numeric_covariance_value_raises_parse_error(self):
        text = (FIXTURES / "oem_g13_covariance.kvn").read_text(encoding="utf-8")
        malformed = text.replace("3.3313494e-04", "NOTANUMBER")
        assert malformed != text
        with pytest.raises(ParseError):
            KVNOEMReader().read_string(malformed)

    def test_wrong_covariance_element_count_raises_parse_error(self):
        text = (FIXTURES / "oem_g13_covariance.kvn").read_text(encoding="utf-8")
        # Drop one element from the first matrix's last row (21 -> 20).
        malformed = text.replace(
            "-3.0413460e-07 -4.9894969e-07  3.5403109e-07  1.8692631e-10  "
            "1.0088625e-10  6.2244443e-10",
            "-3.0413460e-07 -4.9894969e-07  3.5403109e-07  1.8692631e-10  1.0088625e-10",
        )
        assert malformed != text
        with pytest.raises(ParseError):
            KVNOEMReader().read_string(malformed)
