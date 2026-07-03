"""
Unit tests for the XML OEM writer adapter.

Instantiates ``XMLOEMWriter`` directly (as opposed to the high-level
``write()`` dispatch tested in ``tests/io/test_writer.py``) and exercises
``write()`` / ``write_string()`` including a round-trip through
``XMLOEMReader``.

Module under test:
  src/ccsds_data_messages/io/xml/oem_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_oem

from ccsds_data_messages import OEM
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml.oem_reader import XMLOEMReader
from ccsds_data_messages.io.xml.oem_writer import XMLOEMWriter

if TYPE_CHECKING:
    from pathlib import Path


class TestXMLOEMWriter:
    def test_write_string_returns_non_empty_str(self):
        writer = XMLOEMWriter()
        result = writer.write_string(make_oem())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_contains_oem_root_element(self):
        writer = XMLOEMWriter()
        result = writer.write_string(make_oem())
        assert "<oem" in result or "<OEM" in result

    def test_write_creates_file(self, tmp_path: Path):
        writer = XMLOEMWriter()
        path = tmp_path / "out.xml"
        writer.write(make_oem(), path)
        content = path.read_text(encoding="utf-8")
        assert "<oem" in content or "<OEM" in content

    def test_write_round_trips_through_reader(self, tmp_path: Path):
        writer = XMLOEMWriter()
        reader = XMLOEMReader()
        original = make_oem(n_lines=4)
        path = tmp_path / "out.xml"
        writer.write(original, path)
        parsed = reader.read(path)
        assert isinstance(parsed, OEM)
        assert parsed.header.originator == original.header.originator
        assert len(parsed.segments) == len(original.segments)
        original_lines = original.segments[0].ephemeris_data.ephemeris_data_lines
        parsed_lines = parsed.segments[0].ephemeris_data.ephemeris_data_lines
        assert len(parsed_lines) == len(original_lines)
        assert parsed_lines[0].x == pytest.approx(original_lines[0].x)

    def test_write_string_round_trips_through_reader(self):
        writer = XMLOEMWriter()
        reader = XMLOEMReader()
        original = make_oem()
        content = writer.write_string(original)
        parsed = reader.read_string(content)
        assert (
            parsed.segments[0].metadata.object_name
            == original.segments[0].metadata.object_name
        )

    def test_write_string_honors_include_units_option(self):
        """include_units=True annotates numeric elements with unit attributes."""
        writer = XMLOEMWriter()
        options = WriterOptions(include_units=True)
        result = writer.write_string(make_oem(), options=options)
        assert 'units="km"' in result
