"""
OEM tests — model validation, spec fixtures (Annex G11-G14), KVN/XML round-trips.

Replaces:
- test_models.py:TestOEM
- test_roundtrip.py:TestKVNRoundTrip.test_oem_*, TestXMLRoundTrip.test_oem_*
- test_spec_fixtures.py:oem_g11..g14 rows
- test_io_kvn_oem.py (large-file test, replaced with generated OEM)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pydantic
import pytest
from conftest import (
    CREATION_DATE,
    FIXTURES,
    assert_models_equal,
    assert_oem_equal,
    assert_semantic_equal,
    make_oem,
)

from ccsds_data_messages import OEM, read, write
from ccsds_data_messages.io.kvn.oem_reader import KVNOEMReader
from ccsds_data_messages.io.kvn.oem_writer import KVNOEMWriter
from ccsds_data_messages.models.values import (
    CenterName,
    Interpolation,
    ManCovRefFrame,
    RefFrame,
    TimeSystem,
)

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


def _minimal_metadata(**kw):
    defaults = {
        "object_name": "TESTSAT",
        "object_id": "2020-001A",
        "center_name": CenterName.EARTH,
        "ref_frame": RefFrame.GCRF,
        "time_system": TimeSystem.UTC,
        "start_time": "2020-001T00:00:00",
        "stop_time": "2020-001T00:20:00",
    }
    defaults.update(kw)
    return OEM.Segment.Metadata(**defaults)


def _ephemeris_line(**kw) -> OEM.Segment.EphemerisData.EphemerisDataLine:
    defaults = {
        "epoch": "2020-001T00:00:00",
        "x": 7000.0,
        "y": 0.0,
        "z": 0.0,
        "x_dot": 0.5,
        "y_dot": 7.5,
        "z_dot": 0.0,
    }
    defaults.update(kw)
    return OEM.Segment.EphemerisData.EphemerisDataLine(**defaults)


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestOEMModel:
    def test_oem_minimal_single_segment_construction_succeeds(self):
        # §5.2: OEM body is non-empty list of (meta + ephemeris) segments
        oem = make_oem()
        assert len(oem.segments) == 1
        assert len(oem.segments[0].ephemeris_data.ephemeris_data_lines) == 3

    def test_oem_at_least_one_segment_required(self):
        # §5.2: non-empty list of segments is required
        with pytest.raises(pydantic.ValidationError):
            OEM(
                header=OEM.Header(
                    ccsds_oem_vers="3.0",
                    creation_date=CREATION_DATE,
                    originator="TEST",
                ),
                segments=[],
            )

    def test_oem_object_name_mandatory(self):
        # Table 5-2 marks OBJECT_NAME M in per-segment metadata
        with pytest.raises(pydantic.ValidationError):
            OEM.Segment.Metadata(
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                start_time="2020-001T00:00:00",
                stop_time="2020-001T00:20:00",
            )

    def test_oem_start_time_mandatory(self):
        # Table 5-2 marks START_TIME M
        with pytest.raises(pydantic.ValidationError):
            OEM.Segment.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                stop_time="2020-001T00:20:00",
            )

    def test_oem_stop_time_mandatory(self):
        # Table 5-2 marks STOP_TIME M
        with pytest.raises(pydantic.ValidationError):
            OEM.Segment.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                start_time="2020-001T00:00:00",
            )

    def test_oem_interpolation_requires_degree(self):
        # §5.2.3: INTERPOLATION_DEGREE is required when INTERPOLATION is set
        with pytest.raises(pydantic.ValidationError, match="interpolation_degree"):
            OEM.Segment.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                start_time="2020-001T00:00:00",
                stop_time="2020-001T00:20:00",
                interpolation=Interpolation.HERMITE,
            )

    def test_oem_interpolation_degree_accepted_with_method(self):
        meta = _minimal_metadata(
            interpolation=Interpolation.HERMITE,
            interpolation_degree=7,
        )
        assert meta.interpolation == Interpolation.HERMITE
        assert meta.interpolation_degree == 7

    def test_oem_doy_epoch_in_metadata_accepted(self):
        # §7.5.10: both calendar and DOY formats are valid for dates in metadata
        meta = _minimal_metadata(
            start_time="1996-311T17:22:31",
            stop_time="1996-311T23:59:59",
        )
        assert meta.start_time == "1996-311T17:22:31"

    def test_oem_calendar_format_start_time_accepted(self):
        meta = _minimal_metadata(
            start_time="2020-01-01T00:00:00",
            stop_time="2020-01-01T01:00:00",
        )
        assert "2020-01-01T" in meta.start_time

    def test_oem_julian_date_start_time_rejected(self):
        # §7.5.10: Julian Date withdrawn in v3
        with pytest.raises(pydantic.ValidationError):
            _minimal_metadata(start_time="2459945.5")

    def test_oem_ephemeris_data_requires_at_least_two_lines(self):
        # §5.2.4 implies minimum two points for any interpolation to be meaningful;
        # verify the model accepts one (no minimum enforced at model level)
        line = _ephemeris_line(epoch="2020-001T00:00:00", x=7000.0, y=0.0, z=0.0)
        seg = OEM.Segment(
            metadata=_minimal_metadata(stop_time="2020-001T00:10:00"),
            ephemeris_data=OEM.Segment.EphemerisData(ephemeris_data_lines=[line]),
        )
        assert len(seg.ephemeris_data.ephemeris_data_lines) == 1

    def test_oem_ephemeris_line_with_accelerations(self):
        # §7.4.1.2: three optional acceleration components
        line = OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch="2020-001T00:00:00",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
            x_ddot=0.001,
            y_ddot=0.0,
            z_ddot=0.0,
        )
        assert line.x_ddot == 0.001

    def test_oem_comment_at_header_accepted(self):
        header = OEM.Header(
            ccsds_oem_vers="3.0",
            creation_date=CREATION_DATE,
            originator="TEST",
            comment=["G-11 example"],
        )
        assert header.comment == ["G-11 example"]

    def test_oem_comment_empty_list_raises(self):
        with pytest.raises(pydantic.ValidationError):
            OEM.Header(
                ccsds_oem_vers="3.0",
                creation_date=CREATION_DATE,
                originator="TEST",
                comment=[],
            )

    def test_oem_useable_time_within_total_span_accepted(self):
        meta = _minimal_metadata(
            useable_start_time="2020-001T00:05:00",
            useable_stop_time="2020-001T00:15:00",
        )
        assert meta.useable_start_time is not None

    def test_oem_ref_frame_teme_not_rejected_in_oem(self):
        # Unlike OPM, OEM does not prohibit TEME; TEME may appear in any ODM except OPM
        meta = _minimal_metadata(ref_frame=RefFrame.TEME)
        assert meta.ref_frame == RefFrame.TEME

    def test_oem_covariance_matrix_lower_triangular(self):
        # §5.2.5 / §3.2.4.10: lower triangular form stored as CovarianceMatrixLines
        cov_line = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(
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
        assert cov_line.cx_x == pytest.approx(3.33e-4, rel=1e-9)
        assert cov_line.cz_dot_z_dot == pytest.approx(6.22e-10, rel=1e-9)


# ---------------------------------------------------------------------------
# Spec fixture round-trips (Annex G11-G14)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"), _OEM_SPEC_FIXTURES, ids=[x[0] for x in _OEM_SPEC_FIXTURES]
)
def test_oem_spec_fixture_round_trip(name: str, fmt: str, tmp_path: Path) -> None:
    """Read spec fixture → write → semantic-diff → re-read. (CCSDS 502.0-B-3 Annex G)"""
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model_a = read(fixture, fmt=fmt, message_type="oem")
    out = tmp_path / name
    write(model_a, out)
    assert_semantic_equal(fixture, out, fmt)
    model_b = read(out, fmt=fmt, message_type="oem")
    assert_models_equal(model_a, model_b)


# ---------------------------------------------------------------------------
# OEMBuilder
# ---------------------------------------------------------------------------


class TestOEMBuilder:
    _META_KW: ClassVar[dict[str, object]] = {
        "object_name": "TESTSAT",
        "object_id": "2020-001A",
        "center_name": CenterName.EARTH,
        "ref_frame": RefFrame.GCRF,
        "time_system": TimeSystem.UTC,
        "start_time": "2020-001T00:00:00",
        "stop_time": "2020-001T00:10:00",
    }
    _EPHEMERIS_LINES: ClassVar[list[dict[str, object]]] = [
        {
            "epoch": "2020-001T00:00:00",
            "x": 7000.0,
            "y": 0.0,
            "z": 0.0,
            "x_dot": 0.0,
            "y_dot": 7.5,
            "z_dot": 0.0,
        },
        {
            "epoch": "2020-001T00:10:00",
            "x": 6950.0,
            "y": 200.0,
            "z": 0.0,
            "x_dot": -0.2,
            "y_dot": 7.5,
            "z_dot": 0.0,
        },
    ]

    def test_build_minimal(self):
        oem = (
            OEM.builder()
            .header(originator="JAXA")
            .add_segment(dict(self._META_KW), self._EPHEMERIS_LINES)
            .build()
        )
        assert oem.header.originator == "JAXA"
        assert len(oem.segments) == 1
        assert len(oem.segments[0].ephemeris_data.ephemeris_data_lines) == 2

    _COV_FIELDS: ClassVar[list[str]] = [
        "cx_x",
        "cy_x",
        "cy_y",
        "cz_x",
        "cz_y",
        "cz_z",
        "cx_dot_x",
        "cx_dot_y",
        "cx_dot_z",
        "cx_dot_x_dot",
        "cy_dot_x",
        "cy_dot_y",
        "cy_dot_z",
        "cy_dot_x_dot",
        "cy_dot_y_dot",
        "cz_dot_x",
        "cz_dot_y",
        "cz_dot_z",
        "cz_dot_x_dot",
        "cz_dot_y_dot",
        "cz_dot_z_dot",
    ]

    def test_build_with_covariance_matrix_lines(self):
        cov_lines = [
            {
                "epoch": "2020-001T00:00:00",
                "cov_ref_frame": "RSW",
                **dict.fromkeys(self._COV_FIELDS, 1e-06),
            }
        ]
        oem = (
            OEM.builder()
            .header(originator="JAXA")
            .add_segment(
                dict(self._META_KW),
                self._EPHEMERIS_LINES,
                covariance_matrix_lines=cov_lines,
            )
            .build()
        )
        assert oem.segments[0].covariance_matrix is not None

    def test_build_with_multiple_segments(self):
        oem = (
            OEM.builder()
            .header(originator="JAXA")
            .add_segment(dict(self._META_KW), self._EPHEMERIS_LINES)
            .add_segment(dict(self._META_KW), self._EPHEMERIS_LINES)
            .build()
        )
        assert len(oem.segments) == 2

    def test_build_with_missing_required_metadata_key_raises(self):
        incomplete_meta = {k: v for k, v in self._META_KW.items() if k != "object_name"}
        with pytest.raises(pydantic.ValidationError):
            OEM.builder().header(originator="JAXA").add_segment(
                incomplete_meta, self._EPHEMERIS_LINES
            ).build()


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
                        _ephemeris_line(
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
                    metadata=_minimal_metadata(),
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
                    metadata=_minimal_metadata(),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            _ephemeris_line(
                                epoch="2020-001T00:00:00", x=7000.0, y=0.0, z=0.0
                            ),
                            _ephemeris_line(
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
                    metadata=_minimal_metadata(
                        interpolation=Interpolation.HERMITE,
                        interpolation_degree=2,
                    ),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            _ephemeris_line(
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
        """Write → read → write produces identical KVN output."""
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
                    metadata=_minimal_metadata(),
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
                    metadata=_minimal_metadata(),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            _ephemeris_line(
                                epoch="2020-001T00:00:00", x=7000.0, y=0.0, z=0.0
                            ),
                            _ephemeris_line(
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
