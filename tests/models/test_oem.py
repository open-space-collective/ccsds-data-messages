"""
OEM model-validation and builder unit tests.

Replaces the model-validation and builder portions of the former
tests/test_oem.py.
"""

from __future__ import annotations

from typing import ClassVar

import pydantic
import pytest
from conftest import CREATION_DATE
from conftest import make_oem
from conftest import make_oem_ephemeris_line
from conftest import make_oem_metadata
from conftest import make_oem_segment

from ccsds_data_messages import OEM
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import Interpolation
from ccsds_data_messages.models.values import ManCovRefFrame
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestOEMModel:
    def test_oem_minimal_single_segment_construction_succeeds(self):
        # Section 5.2: OEM body is non-empty list of (meta + ephemeris) segments
        oem = make_oem()
        assert len(oem.segments) == 1
        assert len(oem.segments[0].ephemeris_data.ephemeris_data_lines) == 3

    def test_oem_at_least_one_segment_required(self):
        # Section 5.2: non-empty list of segments is required
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
        # Section 5.2.3: INTERPOLATION_DEGREE is required when INTERPOLATION is set
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
        meta = make_oem_metadata(
            interpolation=Interpolation.HERMITE,
            interpolation_degree=7,
        )
        assert meta.interpolation == Interpolation.HERMITE
        assert meta.interpolation_degree == 7

    def test_oem_doy_epoch_in_metadata_accepted(self):
        # Section 7.5.10: both calendar and DOY formats are valid for dates in metadata
        meta = make_oem_metadata(
            start_time="1996-311T17:22:31",
            stop_time="1996-311T23:59:59",
        )
        assert meta.start_time == "1996-311T17:22:31"

    def test_oem_calendar_format_start_time_accepted(self):
        meta = make_oem_metadata(
            start_time="2020-01-01T00:00:00",
            stop_time="2020-01-01T01:00:00",
        )
        assert "2020-01-01T" in meta.start_time

    def test_oem_julian_date_start_time_rejected(self):
        # start_time is absolute-only (CCSDSDate); section 7.5.10 defines only the
        # calendar and day-of-year formats, so a bare decimal is rejected.
        with pytest.raises(pydantic.ValidationError):
            make_oem_metadata(start_time="2459945.5")

    def test_oem_ephemeris_data_requires_at_least_two_lines(self):
        # Section 5.2.4 implies minimum two points for any interpolation to be meaningful;
        # verify the model accepts one (no minimum enforced at model level)
        line = make_oem_ephemeris_line(epoch="2020-001T00:00:00", x=7000.0, y=0.0, z=0.0)
        seg = OEM.Segment(
            metadata=make_oem_metadata(stop_time="2020-001T00:10:00"),
            ephemeris_data=OEM.Segment.EphemerisData(ephemeris_data_lines=[line]),
        )
        assert len(seg.ephemeris_data.ephemeris_data_lines) == 1

    def test_oem_ephemeris_line_with_accelerations(self):
        # Section 7.4.1.2: three optional acceleration components
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
        meta = make_oem_metadata(
            useable_start_time="2020-001T00:05:00",
            useable_stop_time="2020-001T00:15:00",
        )
        assert meta.useable_start_time is not None

    def test_oem_useable_interval_overlap_falls_back_to_total_span_when_omitted(self):
        # Section 5.2.4.4/7.5.10: an omitted USEABLE_START_TIME/USEABLE_STOP_TIME means
        # "all data is assumed valid", so the overlap check must fall back to the
        # segment's total start_time/stop_time rather than skip the check.
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        seg1 = make_oem_segment(
            start_time="2020-001T00:00:00",
            stop_time="2020-001T00:20:00",
            # useable_stop_time omitted -> falls back to stop_time="00:20:00"
        )
        seg2 = make_oem_segment(
            start_time="2020-001T00:10:00",
            stop_time="2020-001T00:30:00",
            # useable_start_time omitted -> falls back to start_time="00:10:00"
        )
        with pytest.raises(pydantic.ValidationError, match="must not overlap"):
            OEM(header=header, segments=[seg1, seg2])

    def test_oem_useable_interval_shared_boundary_accepted(self):
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        seg1 = make_oem_segment(
            start_time="2020-001T00:00:00", stop_time="2020-001T00:20:00"
        )
        seg2 = make_oem_segment(
            start_time="2020-001T00:20:00", stop_time="2020-001T00:40:00"
        )
        oem = OEM(header=header, segments=[seg1, seg2])
        assert len(oem.segments) == 2

    def test_oem_overlapping_raw_spans_accepted_when_useable_intervals_disjoint(self):
        # Section 5.2.4.4: STOP_TIME of segment 1 may exceed START_TIME of segment 2 (raw
        # spans overlapping, e.g. for interpolation padding) as long as the
        # explicit USEABLE_STOP_TIME/USEABLE_START_TIME themselves do not overlap.
        header = OEM.Header(
            ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
        )
        seg1 = make_oem_segment(
            start_time="2020-001T00:00:00",
            stop_time="2020-001T00:25:00",  # raw span extends past seg2's start
            useable_start_time="2020-001T00:00:00",
            useable_stop_time="2020-001T00:20:00",
        )
        seg2 = make_oem_segment(
            start_time="2020-001T00:15:00",  # raw span starts before seg1's stop
            stop_time="2020-001T00:40:00",
            useable_start_time="2020-001T00:20:00",
            useable_stop_time="2020-001T00:40:00",
        )
        oem = OEM(header=header, segments=[seg1, seg2])
        assert len(oem.segments) == 2

    def test_oem_ref_frame_teme_not_rejected_in_oem(self):
        # Unlike OPM, OEM does not prohibit TEME; TEME may appear in any ODM except OPM
        meta = make_oem_metadata(ref_frame=RefFrame.TEME)
        assert meta.ref_frame == RefFrame.TEME

    def test_oem_covariance_matrix_lower_triangular(self):
        # Section 5.2.5 / section 3.2.4.10: lower triangular form stored as CovarianceMatrixLines
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
        # Second segment's span must not overlap the first's (5.2.4.4); a shared
        # boundary is permitted.
        second_meta = dict(self._META_KW)
        second_meta["start_time"] = "2020-001T00:10:00"
        second_meta["stop_time"] = "2020-001T00:20:00"
        second_lines = [
            {**self._EPHEMERIS_LINES[0], "epoch": "2020-001T00:10:00"},
            {**self._EPHEMERIS_LINES[1], "epoch": "2020-001T00:20:00"},
        ]
        oem = (
            OEM.builder()
            .header(originator="JAXA")
            .add_segment(dict(self._META_KW), self._EPHEMERIS_LINES)
            .add_segment(second_meta, second_lines)
            .build()
        )
        assert len(oem.segments) == 2

    def test_build_with_missing_required_metadata_key_raises(self):
        incomplete_meta = {k: v for k, v in self._META_KW.items() if k != "object_name"}
        with pytest.raises(pydantic.ValidationError):
            OEM.builder().header(originator="JAXA").add_segment(
                incomplete_meta, self._EPHEMERIS_LINES
            ).build()


class TestOEMGetSegmentForEpoch:
    """get_segment_for_epoch picks the segment whose span contains an epoch (section 5.2.4.6)."""

    @staticmethod
    def _two_segment_oem() -> OEM:
        seg1 = make_oem_segment(
            start_time="2020-001T00:00:00", stop_time="2020-001T00:20:00"
        )
        seg2 = make_oem_segment(
            start_time="2020-001T00:30:00", stop_time="2020-001T00:50:00"
        )
        return OEM(
            header=OEM.Header(
                ccsds_oem_vers="3.0", creation_date=CREATION_DATE, originator="JAXA"
            ),
            segments=[seg1, seg2],
        )

    def test_returns_segment_containing_epoch(self):
        oem = self._two_segment_oem()
        assert oem.get_segment_for_epoch("2020-001T00:10:00") is oem.segments[0]
        assert oem.get_segment_for_epoch("2020-001T00:40:00") is oem.segments[1]

    def test_span_boundaries_are_inclusive(self):
        oem = self._two_segment_oem()
        assert oem.get_segment_for_epoch("2020-001T00:00:00") is oem.segments[0]
        assert oem.get_segment_for_epoch("2020-001T00:50:00") is oem.segments[1]

    def test_epoch_in_gap_or_outside_returns_none(self):
        oem = self._two_segment_oem()
        assert oem.get_segment_for_epoch("2020-001T00:25:00") is None  # inter-segment gap
        assert oem.get_segment_for_epoch("2020-001T01:00:00") is None  # after last

    def test_doy_and_calendar_epoch_equivalent(self):
        oem = self._two_segment_oem()
        # 2020-001 == 2020-01-01; _normalize_epoch reconciles the two formats.
        assert oem.get_segment_for_epoch("2020-01-01T00:10:00") is oem.segments[0]
