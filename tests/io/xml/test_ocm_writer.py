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

import xml.etree.ElementTree as ET  # noqa: S405
from typing import TYPE_CHECKING

from conftest import make_ocm
from conftest import make_ocm_with_trajectory
from conftest import make_ocm_with_trajectory_and_covariance_blocks

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

    def test_write_roundtrips_trajectory_and_covariance_blocks(self, tmp_path: Path):
        """TRAJ_* and COV_* block IDs and per-block keywords are written and read back."""
        writer = XMLOCMWriter()
        model = make_ocm_with_trajectory_and_covariance_blocks()
        path = tmp_path / "out_traj_cov.xml"
        writer.write(model, path)

        # The ID elements must be present in the XML itself, inside the right block, not
        # just survive a round trip (a writer/reader pair agreeing on a wrong tag would pass).
        data = ET.parse(path).getroot().find("body/segment/data")  # noqa: S314
        assert data is not None
        assert [
            (
                b.findtext("TRAJ_ID"),
                b.findtext("TRAJ_PREV_ID"),
                b.findtext("TRAJ_NEXT_ID"),
            )
            for b in data.findall("traj")
        ] == [("TRAJ_001", None, "TRAJ_002"), ("TRAJ_002", "TRAJ_001", None)]
        assert [
            (b.findtext("COV_ID"), b.findtext("COV_PREV_ID"), b.findtext("COV_NEXT_ID"))
            for b in data.findall("cov")
        ] == [("COV_001", None, "COV_002"), ("COV_002", "COV_001", None)]

        back = XMLOCMReader().read(path)
        assert back.trajectory_states is not None
        assert [
            (
                traj.traj_id,
                traj.traj_prev_id,
                traj.traj_next_id,
                str(traj.traj_basis),
                str(traj.traj_ref_frame),
                str(traj.traj_type),
                traj.data_lines,
            )
            for traj in back.trajectory_states
        ] == [
            (
                traj.traj_id,
                traj.traj_prev_id,
                traj.traj_next_id,
                str(traj.traj_basis),
                str(traj.traj_ref_frame),
                str(traj.traj_type),
                traj.data_lines,
            )
            for traj in model.trajectory_states
        ]

        assert back.covariances is not None
        assert [
            (
                cov.cov_id,
                cov.cov_prev_id,
                cov.cov_next_id,
                str(cov.cov_basis),
                str(cov.cov_ref_frame),
                str(cov.cov_type),
                str(cov.cov_ordering),
                cov.cov_units,
                cov.data_lines,
            )
            for cov in back.covariances
        ] == [
            (
                cov.cov_id,
                cov.cov_prev_id,
                cov.cov_next_id,
                str(cov.cov_basis),
                str(cov.cov_ref_frame),
                str(cov.cov_type),
                str(cov.cov_ordering),
                cov.cov_units,
                cov.data_lines,
            )
            for cov in model.covariances
        ]

    def test_write_with_explicit_options(self, tmp_path: Path):
        """An explicit WriterOptions is accepted and still round-trips."""
        writer = XMLOCMWriter()
        model = make_ocm()
        path = tmp_path / "out_opts.xml"
        writer.write(model, path, options=WriterOptions(suppress_defaults=True))

        back = XMLOCMReader().read(path)
        assert back.header.originator == model.header.originator
        assert back.metadata.epoch_tzero == model.metadata.epoch_tzero
