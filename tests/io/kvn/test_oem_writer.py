"""
Unit tests for the KVN OEM writer adapter.

Instantiates ``KVNOEMWriter`` directly (as opposed to the high-level
``write()`` dispatch tested in ``tests/io/test_writer.py``) and exercises
``write()`` / ``write_string()`` including a round-trip through
``KVNOEMReader``.

Module under test:
  src/ccsds_data_messages/io/kvn/oem_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_oem

from ccsds_data_messages import OEM
from ccsds_data_messages.io.kvn.oem_reader import KVNOEMReader
from ccsds_data_messages.io.kvn.oem_writer import KVNOEMWriter
from ccsds_data_messages.io.options import WriterOptions

if TYPE_CHECKING:
    from pathlib import Path


class TestKVNOEMWriter:
    def test_write_string_returns_non_empty_str(self):
        writer = KVNOEMWriter()
        result = writer.write_string(make_oem())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_contains_format_markers(self):
        writer = KVNOEMWriter()
        result = writer.write_string(make_oem())
        assert "CCSDS_OEM_VERS" in result
        assert "META_START" in result
        assert "META_STOP" in result

    def test_write_creates_file_with_version_first_line(self, tmp_path: Path):
        writer = KVNOEMWriter()
        path = tmp_path / "out.oem"
        writer.write(make_oem(), path)
        content = path.read_text(encoding="utf-8")
        first_line = next(line for line in content.splitlines() if line.strip())
        assert first_line.strip().startswith("CCSDS_OEM_VERS")

    def test_write_round_trips_through_reader(self, tmp_path: Path):
        writer = KVNOEMWriter()
        reader = KVNOEMReader()
        original = make_oem(n_lines=4)
        path = tmp_path / "out.oem"
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
        writer = KVNOEMWriter()
        reader = KVNOEMReader()
        original = make_oem()
        content = writer.write_string(original)
        parsed = reader.read_string(content)
        assert (
            parsed.segments[0].metadata.object_name
            == original.segments[0].metadata.object_name
        )

    def test_write_string_honors_align_keywords_option(self):
        """align_keywords=False produces compact single-space keyword lines."""
        writer = KVNOEMWriter()
        options = WriterOptions(align_keywords=False)
        result = writer.write_string(make_oem(), options=options)
        assert "OBJECT_NAME = TESTSAT" in result
