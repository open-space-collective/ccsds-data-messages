"""
Unit tests for the KVN OMM writer adapter.

Instantiates KVNOMMWriter directly (not the high-level write() dispatch) and
verifies KVN format markers plus a write()->read() round-trip.

Modules under test:
  src/ccsds_data_messages/io/kvn/omm_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_omm

from ccsds_data_messages import OMM
from ccsds_data_messages.io.kvn.omm_reader import KVNOMMReader
from ccsds_data_messages.io.kvn.omm_writer import KVNOMMWriter
from ccsds_data_messages.io.options import WriterOptions

if TYPE_CHECKING:
    from pathlib import Path

_REL_TOLERANCE: float = 1e-9


class TestKVNOMMWriter:
    def test_write_string_returns_non_empty_str(self):
        writer = KVNOMMWriter()
        result = writer.write_string(make_omm())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_first_line_is_version_keyword(self):
        """Section 7.3.6: first non-blank line of KVN must be the version keyword."""
        writer = KVNOMMWriter()
        result = writer.write_string(make_omm())
        first_line = next(line for line in result.splitlines() if line.strip())
        assert first_line.strip().startswith("CCSDS_OMM_VERS")

    def test_write_round_trips_through_reader(self, tmp_path: Path):
        writer = KVNOMMWriter()
        reader = KVNOMMReader()
        model = make_omm()
        path = tmp_path / "out.omm"
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

    def test_align_keywords_option_affects_spacing(self):
        """align_keywords=True pads keywords so '=' signs line up in a column."""
        writer = KVNOMMWriter()
        model = make_omm()
        aligned = writer.write_string(model, options=WriterOptions(align_keywords=True))
        compact = writer.write_string(model, options=WriterOptions(align_keywords=False))
        assert " = " in aligned
        # Compact output is never longer than aligned output (no padding added).
        assert len(compact) <= len(aligned)
