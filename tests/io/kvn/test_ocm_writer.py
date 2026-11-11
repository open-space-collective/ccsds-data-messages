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

import re
from typing import TYPE_CHECKING

from conftest import make_ocm
from conftest import make_ocm_with_trajectory
from conftest import make_ocm_with_trajectory_and_covariance_blocks

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

    def test_write_roundtrips_trajectory_and_covariance_blocks(self, tmp_path: Path):
        """TRAJ_* and COV_* block IDs and per-block keywords are written and read back."""
        writer = KVNOCMWriter()
        model = make_ocm_with_trajectory_and_covariance_blocks()
        path = tmp_path / "out_traj_cov.ocm"
        writer.write(model, path)

        # The ID keywords must be present in the KVN text itself, not just survive
        # a round trip (a writer/reader pair agreeing on a wrong keyword would pass).
        text = path.read_text(encoding="utf-8")
        for keyword, value in [
            ("TRAJ_ID", "TRAJ_001"),
            ("TRAJ_NEXT_ID", "TRAJ_002"),
            ("TRAJ_ID", "TRAJ_002"),
            ("TRAJ_PREV_ID", "TRAJ_001"),
            ("COV_ID", "COV_001"),
            ("COV_NEXT_ID", "COV_002"),
            ("COV_ID", "COV_002"),
            ("COV_PREV_ID", "COV_001"),
        ]:
            assert re.search(rf"^\s*{keyword}\s*=\s*{value}\s*$", text, re.MULTILINE), (
                f"{keyword} = {value} not found in written KVN"
            )

        back = KVNOCMReader().read(path)
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
        writer = KVNOCMWriter()
        model = make_ocm()
        path = tmp_path / "out_opts.ocm"
        writer.write(model, path, options=WriterOptions(suppress_defaults=True))

        back = KVNOCMReader().read(path)
        assert back.header.originator == model.header.originator
        assert back.metadata.epoch_tzero == model.metadata.epoch_tzero
