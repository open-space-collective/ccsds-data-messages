"""
Writer-side high-level API tests.

Covers write() format inference from filename extension and write_string().

Modules under test:
  src/ccsds_data_messages/io/writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import make_oem
from conftest import make_opm

from ccsds_data_messages import write
from ccsds_data_messages.io.writer import write_string

if TYPE_CHECKING:
    from pathlib import Path


class TestWrite:
    def test_write_infers_kvn_format_from_extension(self, tmp_path: Path):
        """Section 7.3.6: first non-blank line of KVN must be the version keyword."""
        opm = make_opm()
        path = tmp_path / "out.opm"
        write(opm, path)
        content = path.read_text()
        first_line = next(line for line in content.splitlines() if line.strip())
        assert first_line.strip().startswith("CCSDS_OPM_VERS")

    def test_write_infers_xml_format_from_extension(self, tmp_path: Path):
        """XML output has an <opm ...> root element."""
        opm = make_opm()
        path = tmp_path / "out.xml"
        write(opm, path)
        content = path.read_text()
        assert "<opm" in content or "<OPM" in content

    def test_write_oem_kvn_contains_start_stop_markers(self, tmp_path: Path):
        """KVN OEM must contain META_START / META_STOP delimiters (section 5.2)."""
        oem = make_oem()
        path = tmp_path / "out.oem"
        write(oem, path)
        content = path.read_text()
        assert "META_START" in content
        assert "META_STOP" in content

    def test_write_string_returns_str(self):
        opm = make_opm()
        result = write_string(opm, fmt="kvn")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_xml_returns_xml_content(self):
        opm = make_opm()
        result = write_string(opm, fmt="xml")
        assert isinstance(result, str)
        assert "<opm" in result or "<OPM" in result
