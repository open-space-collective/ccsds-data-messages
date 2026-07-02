"""
OCM serialization round-trip tests (KVN + XML).

Covers spec-fixture round-trips (Annex G15-G20), programmatic KVN/XML
read/write cycles, and the NDM combined-format xfail placeholders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import CREATION_DATE
from conftest import EPOCH
from conftest import FIXTURES
from conftest import assert_models_equal
from conftest import assert_semantic_equal
from conftest import make_ocm

from ccsds_data_messages import OCM
from ccsds_data_messages import read
from ccsds_data_messages import write
from ccsds_data_messages.io.kvn.ocm_reader import KVNOCMReader
from ccsds_data_messages.io.kvn.ocm_writer import KVNOCMWriter
from ccsds_data_messages.models.values import TimeSystem

if TYPE_CHECKING:
    from pathlib import Path

_OCM_READER = KVNOCMReader()
_OCM_WRITER = KVNOCMWriter()

_OCM_KVN_SPEC_FIXTURES_PASSING = [
    "ocm_g15_minimal.kvn",
    "ocm_g16_characteristics.kvn",
    "ocm_g17_deployments.kvn",
    "ocm_g18_multi_traj.kvn",
    "ocm_g19_covariance_histories.kvn",
]
_OCM_KVN_SPEC_FIXTURES_WRITER_GAP: list[str] = []
_OCM_KVN_SPEC_FIXTURES = (
    _OCM_KVN_SPEC_FIXTURES_PASSING + _OCM_KVN_SPEC_FIXTURES_WRITER_GAP
)


# ---------------------------------------------------------------------------
# Spec fixture round-trips (Annex G15-G19, KVN - should pass)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", _OCM_KVN_SPEC_FIXTURES_PASSING)
def test_ocm_kvn_spec_fixture_round_trip(name: str, tmp_path: Path) -> None:
    """Read a spec fixture, write it, semantic-diff, then re-read. (CCSDS 502.0-B-3 Annex G)"""
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model_a = read(fixture, fmt="kvn", message_type="ocm")
    out = tmp_path / name
    write(model_a, out)
    assert_semantic_equal(fixture, out, "kvn")
    model_b = read(out, fmt="kvn", message_type="ocm")
    assert_models_equal(model_a, model_b)


@pytest.mark.parametrize("name", _OCM_KVN_SPEC_FIXTURES_WRITER_GAP)
def test_ocm_kvn_spec_fixture_round_trip_writer_gap(name: str, tmp_path: Path) -> None:
    """Placeholder: all g16-g19 writer gaps are now closed (list is empty)."""
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model_a = read(fixture, fmt="kvn", message_type="ocm")
    out = tmp_path / name
    write(model_a, out)
    assert_semantic_equal(fixture, out, "kvn")
    model_b = read(out, fmt="kvn", message_type="ocm")
    assert_models_equal(model_a, model_b)


# ---------------------------------------------------------------------------
# OCM fixture readability - distinct from round-trip tests above
#
# These tests assert only that fixtures can be *read* and that a write then read
# produces a semantically equal model.  They do NOT assert that the writer
# output matches the original file (that is the xfail round-trip concern).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", _OCM_KVN_SPEC_FIXTURES_WRITER_GAP)
def test_ocm_kvn_spec_fixture_can_be_read(name: str) -> None:
    """
    OCM spec fixtures G16-G19 must be parseable without error.

    These contain physical properties, deployments, multi-trajectory blocks,
    and covariance histories - all sections the reader must handle.
    """
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model = read(fixture, fmt="kvn", message_type="ocm")
    assert model is not None
    assert model.header is not None
    assert model.metadata is not None


@pytest.mark.parametrize("name", _OCM_KVN_SPEC_FIXTURES_WRITER_GAP)
def test_ocm_kvn_spec_fixture_re_read_preserves_model(name: str, tmp_path: Path) -> None:
    """
    Reading the G16-G19 fixture, writing it, and re-reading must yield an equal model.

    A failure here means the writer silently drops or corrupts fields that
    the reader parsed, which is a distinct bug from the semantic-diff failure
    already captured by test_ocm_kvn_spec_fixture_round_trip_writer_gap.
    """
    fixture = FIXTURES / name
    model_a = read(fixture, fmt="kvn", message_type="ocm")
    out = tmp_path / name
    write(model_a, out)
    model_b = read(out, fmt="kvn", message_type="ocm")
    assert_models_equal(model_a, model_b)


def test_ocm_xml_spec_fixture_g20(tmp_path: Path) -> None:
    """Read, write, then semantic-diff the g20 spec fixture (CCSDS 502.0-B-3 Annex G20)."""
    fixture = FIXTURES / "ocm_g20.xml"
    model_a = read(fixture, fmt="xml", message_type="ocm")
    out = tmp_path / "ocm_g20.xml"
    write(model_a, out, fmt="xml")
    assert_semantic_equal(fixture, out, "xml")


@pytest.mark.xfail(reason="NDM combined format not supported", strict=False)
def test_ndm_g21_combined_omm_round_trip(tmp_path: Path) -> None:
    fixture = FIXTURES / "ndm_g21_combined_omm.xml"
    model_a = read(fixture, fmt="xml", message_type="omm")
    out = tmp_path / "ndm_g21.xml"
    write(model_a, out, fmt="xml")


@pytest.mark.xfail(reason="NDM combined format not supported", strict=False)
def test_ndm_g22_combined_all_round_trip(tmp_path: Path) -> None:
    fixture = FIXTURES / "ndm_g22_combined_all.xml"
    read(fixture)


# ---------------------------------------------------------------------------
# KVN round-trips (programmatic)
# ---------------------------------------------------------------------------


class TestOCMKVNRoundTrip:
    def test_minimal_header_metadata(self, tmp_path: Path) -> None:
        """Minimal OCM (header + metadata only) round-trips correctly."""
        ocm = make_ocm()
        path = tmp_path / "test.ocm"
        write(ocm, path)
        back = read(path, message_type="ocm")
        assert back.header.ccsds_ocm_vers == ocm.header.ccsds_ocm_vers
        assert back.metadata.time_system == ocm.metadata.time_system
        assert back.metadata.epoch_tzero == ocm.metadata.epoch_tzero

    def test_with_trajectory_block(self, tmp_path: Path) -> None:
        """OCM with one trajectory block round-trips."""
        ocm = OCM(
            header=OCM.Header(
                ccsds_ocm_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
            ),
            metadata=OCM.Metadata(time_system=TimeSystem.UTC, epoch_tzero=EPOCH),
            trajectory_states=[
                OCM.TrajectoryStateTimeHistory(
                    traj_type="CARTPV",
                    traj_id="PLAN_A",
                    data_lines=[
                        "2020-001T00:00:00 7000.0 0.0 0.0 0.0 7.5 0.0",
                        "2020-001T00:10:00 6990.0 0.0 0.0 0.0 7.5 0.0",
                    ],
                )
            ],
        )
        path = tmp_path / "test.ocm"
        write(ocm, path)
        back = read(path, message_type="ocm")
        assert back.trajectory_states is not None
        assert len(back.trajectory_states) == 1
        assert back.trajectory_states[0].traj_id == "PLAN_A"

    def test_multi_traj_blocks(self, tmp_path: Path) -> None:
        """OCM with two trajectory blocks (G-18 pattern)."""
        ocm = OCM(
            header=OCM.Header(
                ccsds_ocm_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
            ),
            metadata=OCM.Metadata(time_system=TimeSystem.UTC, epoch_tzero=EPOCH),
            trajectory_states=[
                OCM.TrajectoryStateTimeHistory(
                    traj_type="CARTPV",
                    traj_id="PLAN_A",
                    data_lines=["2020-001T00:00:00 7000.0 0.0 0.0 0.0 7.5 0.0"],
                ),
                OCM.TrajectoryStateTimeHistory(
                    traj_type="CARTPV",
                    traj_id="PLAN_B",
                    data_lines=["2020-001T01:00:00 6990.0 0.0 0.0 0.0 7.5 0.0"],
                ),
            ],
        )
        path = tmp_path / "test.ocm"
        write(ocm, path)
        back = read(path, message_type="ocm")
        assert back.trajectory_states is not None
        assert len(back.trajectory_states) == 2
        assert back.trajectory_states[1].traj_id == "PLAN_B"

    def test_idempotent(self, tmp_path: Path) -> None:
        """Write, read, then write again produces identical KVN output."""
        ocm = make_ocm()
        first = _OCM_WRITER.write_string(ocm)
        second = _OCM_WRITER.write_string(_OCM_READER.read_string(first))
        assert first == second


# ---------------------------------------------------------------------------
# XML round-trips
# ---------------------------------------------------------------------------


class TestOCMXMLRoundTrip:
    def test_minimal(self, tmp_path: Path) -> None:
        """Minimal OCM XML round-trip."""
        ocm = make_ocm()
        path = tmp_path / "test.xml"
        write(ocm, path, fmt="xml")
        back = read(path, fmt="xml", message_type="ocm")
        assert back.header.originator == ocm.header.originator
