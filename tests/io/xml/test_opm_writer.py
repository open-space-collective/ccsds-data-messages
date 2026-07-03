"""
Unit tests for the XML OPM writer adapter.

Instantiates ``XMLOPMWriter`` directly (as opposed to the high-level
``write()`` dispatch tested in ``tests/io/test_writer.py``) and exercises
``write()`` / ``write_string()`` including an XML round-trip via ``XMLOPMReader``.

Module under test:
  src/ccsds_data_messages/io/xml/opm_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_opm

from ccsds_data_messages import OPM
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml.opm_reader import XMLOPMReader
from ccsds_data_messages.io.xml.opm_writer import XMLOPMWriter

if TYPE_CHECKING:
    from pathlib import Path


class TestXMLOPMWriter:
    def test_write_string_returns_non_empty_str(self):
        result = XMLOPMWriter().write_string(make_opm())
        assert isinstance(result, str)
        assert result

    def test_write_string_has_opm_root_element(self):
        """OPM/XML output has an <opm ...> root element (section 8.8)."""
        result = XMLOPMWriter().write_string(make_opm())
        assert "<opm" in result or "<OPM" in result

    def test_write_creates_file_that_reads_back(self, tmp_path: Path):
        opm = make_opm()
        path = tmp_path / "out.xml"
        XMLOPMWriter().write(opm, path)
        assert path.exists()
        back = XMLOPMReader().read(path)
        assert back.header.originator == opm.header.originator
        assert back.metadata.object_name == opm.metadata.object_name
        assert back.data.state_vector.x == pytest.approx(opm.data.state_vector.x)

    def test_write_string_round_trips_through_reader(self):
        opm = make_opm()
        content = XMLOPMWriter().write_string(opm)
        back = XMLOPMReader().read_string(content)
        assert back.data.state_vector.z_dot == pytest.approx(opm.data.state_vector.z_dot)

    def test_write_string_without_units_option(self):
        """include_units=False still produces parseable XML."""
        opm = make_opm()
        options = WriterOptions(include_units=False)
        content = XMLOPMWriter().write_string(opm, options=options)
        assert "<opm" in content or "<OPM" in content
        back = XMLOPMReader().read_string(content)
        assert back.metadata.object_name == opm.metadata.object_name

    def test_user_defined_uses_parameter_attribute_and_round_trips(self):
        """User-defined params serialize as <USER_DEFINED parameter="KEY"> (section 3.2.4.12)."""
        opm = make_opm()
        opm = opm.model_copy(
            update={
                "data": opm.data.model_copy(
                    update={
                        "user_defined": OPM.Data.UserDefinedParameters(
                            user_defined={"EARTH_MODEL": "WGS-84"}
                        )
                    }
                )
            }
        )
        content = XMLOPMWriter().write_string(opm)
        assert 'parameter="EARTH_MODEL"' in content
        back = XMLOPMReader().read_string(content)
        assert back.data.user_defined is not None
        assert back.data.user_defined.user_defined == {"EARTH_MODEL": "WGS-84"}
