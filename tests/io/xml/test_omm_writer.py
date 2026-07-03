"""
Unit tests for the XML OMM writer adapter.

Instantiates XMLOMMWriter directly (not the high-level write() dispatch) and
verifies XML format markers plus a write()->read() round-trip.

Modules under test:
  src/ccsds_data_messages/io/xml/omm_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_omm

from ccsds_data_messages import OMM
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml.omm_reader import XMLOMMReader
from ccsds_data_messages.io.xml.omm_writer import XMLOMMWriter

if TYPE_CHECKING:
    from pathlib import Path

_REL_TOLERANCE: float = 1e-9


class TestXMLOMMWriter:
    def test_write_string_returns_non_empty_str(self):
        writer = XMLOMMWriter()
        result = writer.write_string(make_omm())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_has_omm_root_element(self):
        writer = XMLOMMWriter()
        result = writer.write_string(make_omm())
        assert "<omm" in result or "<OMM" in result

    def test_write_round_trips_through_reader(self, tmp_path: Path):
        writer = XMLOMMWriter()
        reader = XMLOMMReader()
        model = make_omm()
        path = tmp_path / "out.xml"
        writer.write(model, path)
        back = reader.read(path)
        assert isinstance(back, OMM)
        assert back.header.originator == model.header.originator
        assert back.metadata.object_name == model.metadata.object_name
        assert back.metadata.mean_element_theory == model.metadata.mean_element_theory
        mke_in = model.data.mean_keplerian_elements
        mke_out = back.data.mean_keplerian_elements
        assert mke_out.semi_major_axis == pytest.approx(
            mke_in.semi_major_axis, rel=_REL_TOLERANCE
        )
        assert mke_out.eccentricity == pytest.approx(
            mke_in.eccentricity, rel=_REL_TOLERANCE
        )
        assert mke_out.inclination == pytest.approx(
            mke_in.inclination, rel=_REL_TOLERANCE
        )

    def test_include_units_option_toggles_unit_attributes(self):
        """include_units=True annotates numeric elements with units attributes."""
        writer = XMLOMMWriter()
        model = make_omm()
        with_units = writer.write_string(model, options=WriterOptions(include_units=True))
        without_units = writer.write_string(
            model, options=WriterOptions(include_units=False)
        )
        assert 'units="deg"' in with_units
        assert 'units="deg"' not in without_units

    def test_user_defined_uses_parameter_attribute_and_round_trips(self):
        """User-defined params serialize as <USER_DEFINED parameter="KEY"> (section 4.2.4.10)."""
        model = make_omm()
        model = model.model_copy(
            update={
                "data": model.data.model_copy(
                    update={
                        "user_defined": OMM.Data.UserDefinedParameters(
                            user_defined={"EARTH_MODEL": "WGS-84"}
                        )
                    }
                )
            }
        )
        content = XMLOMMWriter().write_string(model)
        assert 'parameter="EARTH_MODEL"' in content
        back = XMLOMMReader().read_string(content)
        assert back.data.user_defined is not None
        assert back.data.user_defined.user_defined == {"EARTH_MODEL": "WGS-84"}
