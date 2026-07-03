"""
Unit tests for the KVN OCM writer adapter.

Instantiates ``KVNOCMWriter`` directly (as opposed to the high-level
``write()`` dispatch tested in ``tests/io/test_writer.py``) and exercises
``write()`` / ``write_string()``, including a round-trip back through
``KVNOCMReader``.

Module under test:
  src/ccsds_data_messages/io/kvn/ocm_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import make_ocm
from conftest import make_ocm_with_trajectory

from ccsds_data_messages import OCM
from ccsds_data_messages.io.kvn.ocm_reader import KVNOCMReader
from ccsds_data_messages.io.kvn.ocm_writer import KVNOCMWriter
from ccsds_data_messages.io.options import WriterOptions

if TYPE_CHECKING:
    from pathlib import Path


class TestKVNOCMWriter:
    def test_write_string_returns_non_empty_str(self):
        writer = KVNOCMWriter()
        result = writer.write_string(make_ocm())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_first_line_is_version_keyword(self):
        """Section 7.3.6: first non-blank line of KVN must be the version keyword."""
        writer = KVNOCMWriter()
        result = writer.write_string(make_ocm())
        first_line = next(line for line in result.splitlines() if line.strip())
        assert first_line.strip().startswith("CCSDS_OCM_VERS")

    def test_write_string_contains_meta_delimiters(self):
        """OCM metadata is delimited by META_START / META_STOP (section 6.2.4)."""
        writer = KVNOCMWriter()
        result = writer.write_string(make_ocm())
        assert "META_START" in result
        assert "META_STOP" in result

    def test_write_roundtrips_through_reader(self, tmp_path: Path):
        writer = KVNOCMWriter()
        model = make_ocm_with_trajectory()
        path = tmp_path / "out.ocm"
        writer.write(model, path)

        back = KVNOCMReader().read(path)
        assert isinstance(back, OCM)
        assert back.header.originator == model.header.originator
        assert back.metadata.object_name == model.metadata.object_name
        assert back.metadata.epoch_tzero == model.metadata.epoch_tzero
        assert back.trajectory_states is not None
        assert len(back.trajectory_states) == 1
        assert (
            back.trajectory_states[0].data_lines == model.trajectory_states[0].data_lines
        )

    def test_write_with_explicit_options(self, tmp_path: Path):
        """An explicit WriterOptions is accepted and still round-trips."""
        writer = KVNOCMWriter()
        model = make_ocm()
        path = tmp_path / "out_opts.ocm"
        writer.write(model, path, options=WriterOptions(suppress_defaults=True))

        back = KVNOCMReader().read(path)
        assert back.header.originator == model.header.originator
        assert back.metadata.epoch_tzero == model.metadata.epoch_tzero
