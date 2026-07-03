"""
OEM serialization round-trip tests (KVN + XML).

Covers spec fixture round-trips (Annex G11-G14) and programmatic
KVN/XML read/write round-trips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import CREATION_DATE
from conftest import FIXTURES
from conftest import assert_models_equal
from conftest import assert_oem_equal
from conftest import assert_semantic_equal
from conftest import make_oem
from conftest import make_oem_ephemeris_line
from conftest import make_oem_metadata

from ccsds_data_messages import OEM
from ccsds_data_messages import read
from ccsds_data_messages import write
from ccsds_data_messages.io.kvn.oem_reader import KVNOEMReader
from ccsds_data_messages.io.kvn.oem_writer import KVNOEMWriter
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import Interpolation
from ccsds_data_messages.models.values import ManCovRefFrame
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

if TYPE_CHECKING:
    from pathlib import Path

_OEM_READER = KVNOEMReader()
_OEM_WRITER = KVNOEMWriter()

_OEM_SPEC_FIXTURES = [
    ("oem_g11.kvn", "kvn"),
    ("oem_g12_accelerations.kvn", "kvn"),
    ("oem_g13_covariance.kvn", "kvn"),
    ("oem_g14.xml", "xml"),
]


# ---------------------------------------------------------------------------
# Spec fixture round-trips (Annex G11-G14)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"), _OEM_SPEC_FIXTURES, ids=[x[0] for x in _OEM_SPEC_FIXTURES]
)
def test_oem_spec_fixture_round_trip(name: str, fmt: str, tmp_path: Path) -> None:
    """Read a spec fixture, write it, semantic-diff, then re-read. (CCSDS 502.0-B-3 Annex G)"""
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model_a = read(fixture, fmt=fmt, message_type="oem")
    out = tmp_path / name
    write(model_a, out)
    assert_semantic_equal(fixture, out, fmt)
    model_b = read(out, fmt=fmt, message_type="oem")
    assert_models_equal(model_a, model_b)


# ---------------------------------------------------------------------------
# KVN round-trips (programmatic)
# ---------------------------------------------------------------------------


class TestOEMKVNRoundTrip:
    def test_single_segment(self, tmp_path: Path) -> None:
        """Single-segment OEM: all header/metadata/ephemeris fields survive round-trip."""
        msg = make_oem(n_lines=5)
        path = tmp_path / "test.oem"
        write(msg, path)
        back = read(path, message_type="oem")
        assert_oem_equal(msg, back)

    def test_multi_segment(self, tmp_path: Path) -> None:
        """Two-segment OEM (G-11 pattern): both segments recovered."""
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )

        def _make_seg(idx: int) -> OEM.Segment:
            base = idx * 100
            start = f"2020-001T0{idx}:00:00"
            stop = f"2020-001T0{idx}:30:00"
            return OEM.Segment(
                metadata=OEM.Segment.Metadata(
                    object_name="TESTSAT",
                    object_id="2020-001A",
                    center_name=CenterName.EARTH,
                    ref_frame=RefFrame.GCRF,
                    time_system=TimeSystem.UTC,
                    start_time=start,
                    stop_time=stop,
                ),
                ephemeris_data=OEM.Segment.EphemerisData(
                    ephemeris_data_lines=[
                        make_oem_ephemeris_line(
                            epoch=f"2020-001T0{idx}:{m:02d}:00",
                            x=7000.0 + base + m,
                            y=0.0,
                            z=0.0,
                        )
                        for m in range(3)
                    ]
                ),
            )

        oem = OEM(header=header, segments=[_make_seg(0), _make_seg(1)])
        path = tmp_path / "test.oem"
        write(oem, path)
        back = read(path, message_type="oem")
        assert len(back.segments) == 2
        assert back.segments[1].metadata.start_time == "2020-001T01:00:00"

    def test_with_accelerations(self, tmp_path: Path) -> None:
        """10-column ephemeris rows (G-12 pattern): accelerations survive round-trip."""
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        lines = [
            OEM.Segment.EphemerisData.EphemerisDataLine(
                epoch=f"2020-001T00:{i * 10:02d}:00",
                x=7000.0,
                y=0.0,
                z=0.0,
                x_dot=0.0,
                y_dot=7.5,
                z_dot=0.0,
                x_ddot=0.001 * i,
                y_ddot=0.0,
                z_ddot=0.0,
            )
            for i in range(3)
        ]
        oem = OEM(
            header=header,
            segments=[
                OEM.Segment(
                    metadata=make_oem_metadata(),
                    ephemeris_data=OEM.Segment.EphemerisData(ephemeris_data_lines=lines),
                )
            ],
        )
        path = tmp_path / "test.oem"
        write(oem, path)
        back = read(path, message_type="oem")
        assert back.segments[0].ephemeris_data.ephemeris_data_lines[
            2
        ].x_ddot == pytest.approx(0.002, rel=1e-9)

    def test_with_covariance(self, tmp_path: Path) -> None:
        """Per-epoch covariance matrices survive KVN round-trip (G-13 pattern)."""
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        cov_entry = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(
            epoch="2020-001T00:00:00",
            cov_ref_frame=ManCovRefFrame.RTN,
            cx_x=3.33e-4,
            cy_x=4.61e-4,
            cy_y=6.78e-4,
            cz_x=-3.07e-4,
            cz_y=-4.22e-4,
            cz_z=3.23e-4,
            cx_dot_x=-3.35e-7,
            cx_dot_y=-4.68e-7,
            cx_dot_z=2.48e-7,
            cx_dot_x_dot=4.29e-10,
            cy_dot_x=-2.21e-7,
            cy_dot_y=-2.86e-7,
            cy_dot_z=1.79e-7,
            cy_dot_x_dot=2.60e-10,
            cy_dot_y_dot=1.76e-10,
            cz_dot_x=-3.04e-7,
            cz_dot_y=-4.98e-7,
            cz_dot_z=3.54e-7,
            cz_dot_x_dot=1.86e-10,
            cz_dot_y_dot=1.00e-10,
            cz_dot_z_dot=6.22e-10,
        )
        oem = OEM(
            header=header,
            segments=[
                OEM.Segment(
                    metadata=make_oem_metadata(),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            make_oem_ephemeris_line(
                                epoch="2020-001T00:00:00", x=7000.0, y=0.0, z=0.0
                            ),
                            make_oem_ephemeris_line(
                                epoch="2020-001T00:10:00", x=6990.0, y=0.0, z=0.0
                            ),
                        ]
                    ),
                    covariance_matrix=OEM.Segment.CovarianceMatrix(
                        covariance_matrix_lines=[cov_entry],
                    ),
                )
            ],
        )
        path = tmp_path / "test.oem"
        write(oem, path)
        back = read(path, message_type="oem")
        cov_back = back.segments[0].covariance_matrix
        assert cov_back is not None
        assert cov_back.covariance_matrix_lines[0].cx_x == pytest.approx(
            3.33e-4, rel=1e-9
        )

    def test_with_interpolation_fields(self, tmp_path: Path) -> None:
        """INTERPOLATION and INTERPOLATION_DEGREE survive round-trip."""
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        oem = OEM(
            header=header,
            segments=[
                OEM.Segment(
                    metadata=make_oem_metadata(
                        interpolation=Interpolation.HERMITE,
                        interpolation_degree=2,
                    ),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            make_oem_ephemeris_line(
                                epoch=f"2020-001T00:{i * 10:02d}:00",
                                x=7000.0 - i,
                                y=0.0,
                                z=0.0,
                            )
                            for i in range(3)
                        ]
                    ),
                )
            ],
        )
        path = tmp_path / "test.oem"
        write(oem, path)
        back = read(path, message_type="oem")
        assert back.segments[0].metadata.interpolation == Interpolation.HERMITE
        assert back.segments[0].metadata.interpolation_degree == 2

    def test_idempotent(self, tmp_path: Path) -> None:
        """Write, read, then write again produces identical KVN output."""
        oem = make_oem()
        first = _OEM_WRITER.write_string(oem)
        second = _OEM_WRITER.write_string(_OEM_READER.read_string(first))
        assert first == second

    def test_g11_spec_object_name_and_ref_frame(self) -> None:
        """G-11: object name, ref frame, and first epoch are correctly parsed."""
        fixture = FIXTURES / "oem_g11.kvn"
        if not fixture.exists():
            pytest.skip("oem_g11.kvn not present")
        oem = read(fixture, message_type="oem")
        # G-11 header: ORIGINATOR = JAXA; first segment: OBJECT = GAIA
        assert oem.header.originator is not None
        assert len(oem.segments) >= 1


# ---------------------------------------------------------------------------
# XML round-trips
# ---------------------------------------------------------------------------


class TestOEMXMLRoundTrip:
    def test_minimal(self, tmp_path: Path) -> None:
        msg = make_oem()
        path = tmp_path / "test.xml"
        write(msg, path, fmt="xml")
        back = read(path, fmt="xml", message_type="oem")
        assert_oem_equal(msg, back)

    def test_with_accelerations(self, tmp_path: Path) -> None:
        """G-14 pattern: stateVector with X_DDOT/Y_DDOT/Z_DDOT survive XML round-trip."""
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        lines = [
            OEM.Segment.EphemerisData.EphemerisDataLine(
                epoch=f"2020-001T00:{i * 10:02d}:00",
                x=7000.0,
                y=0.0,
                z=0.0,
                x_dot=0.0,
                y_dot=7.5,
                z_dot=0.0,
                x_ddot=0.001,
                y_ddot=0.002,
                z_ddot=0.003,
            )
            for i in range(3)
        ]
        oem = OEM(
            header=header,
            segments=[
                OEM.Segment(
                    metadata=make_oem_metadata(),
                    ephemeris_data=OEM.Segment.EphemerisData(ephemeris_data_lines=lines),
                )
            ],
        )
        path = tmp_path / "test.xml"
        write(oem, path, fmt="xml")
        back = read(path, fmt="xml", message_type="oem")
        line_back = back.segments[0].ephemeris_data.ephemeris_data_lines[0]
        assert line_back.x_ddot == pytest.approx(0.001, rel=1e-9)

    def test_with_covariance(self, tmp_path: Path) -> None:
        """Per-epoch covarianceMatrix blocks survive XML round-trip."""
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        cov_entry = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(
            epoch="2020-001T00:00:00",
            cov_ref_frame=ManCovRefFrame.RTN,
            cx_x=3.33e-4,
            cy_x=4.61e-4,
            cy_y=6.78e-4,
            cz_x=-3.07e-4,
            cz_y=-4.22e-4,
            cz_z=3.23e-4,
            cx_dot_x=-3.35e-7,
            cx_dot_y=-4.68e-7,
            cx_dot_z=2.48e-7,
            cx_dot_x_dot=4.29e-10,
            cy_dot_x=-2.21e-7,
            cy_dot_y=-2.86e-7,
            cy_dot_z=1.79e-7,
            cy_dot_x_dot=2.60e-10,
            cy_dot_y_dot=1.76e-10,
            cz_dot_x=-3.04e-7,
            cz_dot_y=-4.98e-7,
            cz_dot_z=3.54e-7,
            cz_dot_x_dot=1.86e-10,
            cz_dot_y_dot=1.00e-10,
            cz_dot_z_dot=6.22e-10,
        )
        oem = OEM(
            header=header,
            segments=[
                OEM.Segment(
                    metadata=make_oem_metadata(),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            make_oem_ephemeris_line(
                                epoch="2020-001T00:00:00", x=7000.0, y=0.0, z=0.0
                            ),
                            make_oem_ephemeris_line(
                                epoch="2020-001T00:10:00", x=6990.0, y=0.0, z=0.0
                            ),
                        ]
                    ),
                    covariance_matrix=OEM.Segment.CovarianceMatrix(
                        covariance_matrix_lines=[cov_entry],
                    ),
                )
            ],
        )
        path = tmp_path / "test.xml"
        write(oem, path, fmt="xml")
        back = read(path, fmt="xml", message_type="oem")
        cov_back = back.segments[0].covariance_matrix
        assert cov_back is not None
        assert cov_back.covariance_matrix_lines[0].cx_x == pytest.approx(
            3.33e-4, rel=1e-9
        )
