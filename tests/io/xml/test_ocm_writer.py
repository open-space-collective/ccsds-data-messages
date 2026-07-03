"""
Unit tests for the XML OCM writer adapter.

Instantiates ``XMLOCMWriter`` directly (as opposed to the high-level
``write()`` dispatch tested in ``tests/io/test_writer.py``) and exercises
``write()`` / ``write_string()``, including a round-trip back through
``XMLOCMReader``.

Module under test:
  src/ccsds_data_messages/io/xml/ocm_writer.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import make_ocm
from conftest import make_ocm_with_trajectory

from ccsds_data_messages import OCM
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.io.xml.ocm_reader import XMLOCMReader
from ccsds_data_messages.io.xml.ocm_writer import XMLOCMWriter

if TYPE_CHECKING:
    from pathlib import Path


class TestXMLOCMWriter:
    def test_write_string_returns_non_empty_str(self):
        writer = XMLOCMWriter()
        result = writer.write_string(make_ocm())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_has_ocm_root_element(self):
        writer = XMLOCMWriter()
        result = writer.write_string(make_ocm())
        assert "<ocm" in result or "<OCM" in result

    def test_write_roundtrips_through_reader(self, tmp_path: Path):
        writer = XMLOCMWriter()
        model = make_ocm_with_trajectory()
        path = tmp_path / "out.xml"
        writer.write(model, path)

        back = XMLOCMReader().read(path)
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
        writer = XMLOCMWriter()
        model = make_ocm()
        path = tmp_path / "out_opts.xml"
        writer.write(model, path, options=WriterOptions(suppress_defaults=True))

        back = XMLOCMReader().read(path)
        assert back.header.originator == model.header.originator
        assert back.metadata.epoch_tzero == model.metadata.epoch_tzero
