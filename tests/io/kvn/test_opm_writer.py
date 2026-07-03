"""
Unit tests for the KVN OPM writer adapter.

Instantiates ``KVNOPMWriter`` directly (as opposed to the high-level
``write()`` dispatch tested in ``tests/io/test_writer.py``) and exercises
``write()`` / ``write_string()`` including a KVN round-trip via ``KVNOPMReader``.

Module under test:
  src/ccsds_data_messages/io/kvn/opm_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_opm

from ccsds_data_messages.io.kvn.opm_reader import KVNOPMReader
from ccsds_data_messages.io.kvn.opm_writer import KVNOPMWriter
from ccsds_data_messages.io.options import WriterOptions

if TYPE_CHECKING:
    from pathlib import Path


def _first_non_blank_line(content: str) -> str:
    return next(line for line in content.splitlines() if line.strip())


class TestKVNOPMWriter:
    def test_write_string_returns_non_empty_str(self):
        result = KVNOPMWriter().write_string(make_opm())
        assert isinstance(result, str)
        assert result

    def test_write_string_starts_with_version_keyword(self):
        """Section 7.3.6: first non-blank line of KVN must be the version keyword."""
        result = KVNOPMWriter().write_string(make_opm())
        assert _first_non_blank_line(result).strip().startswith("CCSDS_OPM_VERS")

    def test_write_creates_file_that_reads_back(self, tmp_path: Path):
        opm = make_opm()
        path = tmp_path / "out.opm"
        KVNOPMWriter().write(opm, path)
        assert path.exists()
        back = KVNOPMReader().read(path)
        assert back.header.originator == opm.header.originator
        assert back.metadata.object_name == opm.metadata.object_name
        assert back.data.state_vector.x == pytest.approx(opm.data.state_vector.x)

    def test_write_string_round_trips_through_reader(self):
        opm = make_opm()
        content = KVNOPMWriter().write_string(opm)
        back = KVNOPMReader().read_string(content)
        assert back.data.state_vector.y_dot == pytest.approx(opm.data.state_vector.y_dot)

    def test_write_string_with_options(self):
        """align_keywords=False produces compact, still-parseable output."""
        opm = make_opm()
        options = WriterOptions(align_keywords=False)
        content = KVNOPMWriter().write_string(opm, options=options)
        assert content
        back = KVNOPMReader().read_string(content)
        assert back.metadata.object_name == opm.metadata.object_name
