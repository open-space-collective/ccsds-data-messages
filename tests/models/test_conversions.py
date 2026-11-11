"""
OEM-to-TraCSS-OCM conversion tests.

Module under test: src/ccsds_data_messages/models/conversions.py (oem_to_tracss_ocm)
"""

from __future__ import annotations

import pytest

from ccsds_data_messages import OEM
from ccsds_data_messages import oem_to_tracss_ocm
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import CovarianceOrdering
from ccsds_data_messages.models.values import OrbitalElements
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

CREATION_DATE = "2020-001T12:00:00"

# TraCSS-mandatory kwargs supplied to every oem_to_tracss_ocm() call in this module.
TRACSS_REQUIRED = {
    "traj_basis": "OPERATIONAL",
    "object_designator": "12345",
    "operator": "ORG",
    "owner": "ORG",
    "country": "USA",
    "originator_address": "123 Main St",
    "originator_email": "test@example.com",
    "originator_phone": "+1-555-0000",
    "message_id": "TEST-MSG-001",
}

_COV_LINE_BASE = {
    "cx_x": 1e-6,
    "cy_x": 2e-7,
    "cy_y": 3e-6,
    "cz_x": 4e-7,
    "cz_y": 5e-7,
    "cz_z": 6e-6,
    "cx_dot_x": 7e-9,
    "cx_dot_y": 8e-9,
    "cx_dot_z": 9e-9,
    "cx_dot_x_dot": 1e-11,
    "cy_dot_x": 2e-9,
    "cy_dot_y": 3e-9,
    "cy_dot_z": 4e-9,
    "cy_dot_x_dot": 5e-11,
    "cy_dot_y_dot": 6e-11,
    "cz_dot_x": 7e-9,
    "cz_dot_y": 8e-9,
    "cz_dot_z": 9e-9,
    "cz_dot_x_dot": 1e-11,
    "cz_dot_y_dot": 2e-11,
    "cz_dot_z_dot": 3e-11,
}

_BASE_EPH = {"x": 7000.0, "y": 0.0, "z": 0.0, "x_dot": 0.0, "y_dot": 7.5, "z_dot": 0.0}


def _make_oem(
    *,
    object_name: str = "SAT",
    object_id: str = "2020-001A",
    with_accel: bool = False,
    with_covariance: bool = False,
    extra_segments: list[dict] | None = None,
    n_lines: int = 12,
) -> OEM:
    """
    Build an OEM suitable for oem_to_tracss_ocm().

    Default 12 data lines (hourly, 00:00-11:00) satisfies useable_record_padding=5
    (needs >=11 lines). Uses EME2000 as required by TraCSS; covariance (if any) is in RSW_INERTIAL.
    """
    base_line: dict = dict(**_BASE_EPH)
    if with_accel:
        base_line.update(x_ddot=0.001, y_ddot=0.002, z_ddot=0.003)

    lines = [{"epoch": f"2020-001T{i:02d}:00:00", **base_line} for i in range(n_lines)]

    cov_lines = None
    if with_covariance:
        # RSW_INERTIAL is one of the two COV_REF_FRAMEs TraCSS accepts (table 6).
        cov_lines = [
            {
                "epoch": f"2020-001T{i:02d}:00:00",
                "cov_ref_frame": "RSW_INERTIAL",
                **_COV_LINE_BASE,
            }
            for i in range(n_lines)
        ]

    builder = (
        OEM.builder()
        .header(originator="TEST_ORG", creation_date=CREATION_DATE)
        .add_segment(
            metadata_kwargs={
                "object_name": object_name,
                "object_id": object_id,
                "center_name": CenterName.EARTH,
                "ref_frame": RefFrame.EME2000,
                "time_system": TimeSystem.UTC,
                "start_time": "2020-001T00:00:00",
                "stop_time": f"2020-001T{n_lines - 1:02d}:00:00",
            },
            ephemeris_data_lines=lines,
            covariance_matrix_lines=cov_lines,
        )
    )
    for seg_kwargs in extra_segments or []:
        builder.add_segment(**seg_kwargs)
    return builder.build()


def _make_segment(
    day: str,
    first_hour: int,
    *,
    ref_frame: RefFrame = RefFrame.EME2000,
    cov_ref_frames: str | list[str | None] | None = None,
    with_covariance: bool = True,
    cov_epochs: list[str] | None = None,
) -> dict:
    """
    ``add_segment`` kwargs for a 12-line hourly segment starting at ``2020-<day>T<first_hour>``.

    ``cov_ref_frames`` is one frame for every covariance line, or a per-line list
    (``None`` entries fall back to the segment REF_FRAME). ``cov_epochs`` overrides the
    covariance epochs, which otherwise match the ephemeris epochs one-to-one.
    """
    epochs = [f"2020-{day}T{first_hour + i:02d}:00:00" for i in range(12)]
    seg: dict = {
        "metadata_kwargs": {
            "object_name": "SAT",
            "object_id": "2020-001A",
            "center_name": CenterName.EARTH,
            "ref_frame": ref_frame,
            "time_system": TimeSystem.UTC,
            "start_time": epochs[0],
            "stop_time": epochs[-1],
        },
        "ephemeris_data_lines": [{"epoch": e, **_BASE_EPH} for e in epochs],
    }
    if with_covariance:
        epochs_for_cov = cov_epochs if cov_epochs is not None else epochs
        frames = (
            cov_ref_frames
            if isinstance(cov_ref_frames, list)
            else [cov_ref_frames] * len(epochs_for_cov)
        )
        seg["covariance_matrix_lines"] = [
            {
                "epoch": e,
                **({"cov_ref_frame": f} if f is not None else {}),
                **_COV_LINE_BASE,
            }
            for e, f in zip(epochs_for_cov, frames, strict=True)
        ]
    return seg


def _make_multi_segment_oem(*segments: dict) -> OEM:
    """Build an OEM from ``_make_segment`` kwargs, in order."""
    builder = OEM.builder().header(originator="TEST_ORG", creation_date=CREATION_DATE)
    for seg in segments:
        builder.add_segment(**seg)
    return builder.build()


class TestOemToTracsSOcm:
    def test_minimal_header_and_metadata(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.header.originator == "TEST_ORG"
        assert ocm.header.creation_date == CREATION_DATE
        assert ocm.metadata.object_name == "SAT"
        assert ocm.metadata.international_designator == "2020-001A"
        assert ocm.metadata.time_system == TimeSystem.UTC

    def test_epoch_tzero_equals_first_ephemeris_epoch(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.metadata.epoch_tzero == "2020-001T00:00:00"

    def test_metadata_time_span_derived_from_useable_windows(self):
        # With padding=5 and 12 lines per segment, useable window is lines[5]-lines[6].
        # Segment 0: 00:00-11:00 gives useable 05:00-06:00
        # Extra seg: 12:00-23:00 gives useable 17:00-18:00
        extra_lines = [
            {"epoch": f"2020-001T{12 + i:02d}:00:00", **_BASE_EPH} for i in range(12)
        ]
        extra_seg = {
            "metadata_kwargs": {
                "object_name": "SAT",
                "object_id": "2020-001A",
                "center_name": CenterName.EARTH,
                "ref_frame": RefFrame.EME2000,
                "time_system": TimeSystem.UTC,
                "start_time": "2020-001T12:00:00",
                "stop_time": "2020-001T23:00:00",
            },
            "ephemeris_data_lines": extra_lines,
        }
        oem = _make_oem(extra_segments=[extra_seg])
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.metadata.start_time == "2020-001T05:00:00"
        assert ocm.metadata.stop_time == "2020-001T18:00:00"
        assert len(ocm.trajectory_states) == 2

    def test_cartpv_traj_type_when_no_accelerations(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert len(ocm.trajectory_states) == 1
        traj = ocm.trajectory_states[0]
        assert traj.traj_type == OrbitalElements.CARTPV
        assert len(traj.data_lines) == 12

    def test_cartpv_data_line_format(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.trajectory_states[0].data_lines[0] == (
            "2020-001T00:00:00  7000.000  0.000  0.000  0.000000  7.500000  0.000000"
        )

    def test_cartpva_traj_type_when_accelerations_present(self):
        oem = _make_oem(with_accel=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.trajectory_states[0].traj_type == OrbitalElements.CARTPVA
        for line in ocm.trajectory_states[0].data_lines:
            assert len(line.split()) == 10

    def test_cartpva_data_line_format(self):
        # Locks in the acceleration terms' exact format (MOD-4: x_ddot/y_ddot/z_ddot
        # have no explicit format_spec, so they use the ".15g" fallback) - the
        # token-count check above wouldn't catch a precision/format regression here.
        oem = _make_oem(with_accel=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.trajectory_states[0].data_lines[0] == (
            "2020-001T00:00:00  7000.000  0.000  0.000  0.000000  7.500000  0.000000"
            " 0.001 0.002 0.003"
        )

    def test_segment_metadata_carried_to_traj_block(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        traj = ocm.trajectory_states[0]
        # TraCSS-Spec-002: TRAJ_ID numbered consecutively starting with 1.
        assert traj.traj_id == "1"
        assert traj.center_name == CenterName.EARTH
        assert traj.traj_ref_frame == RefFrame.EME2000

    def test_multiple_segments_carried_to_traj_blocks(self):
        # Second segment follows the default one (00:00-11:00) without overlap and uses a
        # distinct state (x = 7100 km) so lines landing in the wrong block show up.
        extra_lines = [
            {"epoch": f"2020-001T{12 + i:02d}:00:00", **_BASE_EPH, "x": 7100.0}
            for i in range(12)
        ]
        extra_seg = {
            "metadata_kwargs": {
                "object_name": "SAT",
                "object_id": "2020-001A",
                "center_name": CenterName.EARTH,
                "ref_frame": RefFrame.EME2000,
                "time_system": TimeSystem.UTC,
                "start_time": "2020-001T12:00:00",
                "stop_time": "2020-001T23:00:00",
            },
            "ephemeris_data_lines": extra_lines,
        }
        oem = _make_oem(extra_segments=[extra_seg])
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

        assert len(ocm.trajectory_states) == 2
        first, second = ocm.trajectory_states

        # TraCSS-Spec-002: TRAJ_ID numbered consecutively starting with 1.
        assert (first.traj_id, second.traj_id) == ("1", "2")
        for traj in (first, second):
            assert traj.center_name == CenterName.EARTH
            assert traj.traj_ref_frame == RefFrame.EME2000
            assert traj.traj_type == OrbitalElements.CARTPV
            assert traj.traj_basis == "OPERATIONAL"
            assert len(traj.data_lines) == 12

        # One block per segment, in segment order, each holding its own lines.
        assert first.data_lines[0] == (
            "2020-001T00:00:00  7000.000  0.000  0.000  0.000000  7.500000  0.000000"
        )
        assert first.data_lines[-1].startswith("2020-001T11:00:00")
        assert second.data_lines[0] == (
            "2020-001T12:00:00  7100.000  0.000  0.000  0.000000  7.500000  0.000000"
        )
        assert second.data_lines[-1].startswith("2020-001T23:00:00")

        # Default useable_record_padding=5 trims each block independently.
        assert (first.useable_start_time, first.useable_stop_time) == (
            "2020-001T05:00:00",
            "2020-001T06:00:00",
        )
        assert (second.useable_start_time, second.useable_stop_time) == (
            "2020-001T17:00:00",
            "2020-001T18:00:00",
        )

    def test_covariance_block_produced_when_cov_present(self):
        oem = _make_oem(with_covariance=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.covariances is not None
        assert len(ocm.covariances) == 1
        cov = ocm.covariances[0]
        assert cov.cov_type == OrbitalElements.CARTPV
        # TraCSS-Spec-002 table 6: COV_ID is mandatory must be numbered consecutively starting with 1.
        assert cov.cov_id == "1"
        # TraCSS-Spec-002 table 6: COV_ORDERING = LTM, COV_UNITS fixed for CARTPV.
        assert cov.cov_ordering == CovarianceOrdering.LTM
        assert cov.cov_units == "[km,km,km,km/s,km/s,km/s]"
        # One OCM covariance line per OEM covariance matrix (_make_oem default: 12).
        assert len(cov.data_lines) == len(
            oem.segments[0].covariance_matrix.covariance_matrix_lines
        )
        assert len(cov.data_lines) == 12
        # epoch + 21 LTM elements = 22 tokens
        tokens = cov.data_lines[0].split()
        assert len(tokens) == 22

    def test_covariance_data_line_format(self):
        # Locks in the exact " .15e" covariance format (MOD-4) - the token-count
        # check above wouldn't catch a precision regression in any of the 21 elements.
        oem = _make_oem(with_covariance=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.covariances[0].data_lines[0] == (
            "2020-001T00:00:00"
            "  1.000000000000000e-06  2.000000000000000e-07  3.000000000000000e-06"
            "  4.000000000000000e-07  5.000000000000000e-07  6.000000000000000e-06"
            "  7.000000000000000e-09  8.000000000000000e-09  9.000000000000000e-09"
            "  9.999999999999999e-12  2.000000000000000e-09  3.000000000000000e-09"
            "  4.000000000000000e-09  5.000000000000000e-11  6.000000000000000e-11"
            "  7.000000000000000e-09  8.000000000000000e-09  9.000000000000000e-09"
            "  9.999999999999999e-12  2.000000000000000e-11  3.000000000000000e-11"
        )

    def test_no_covariance_when_absent(self):
        oem = _make_oem(with_covariance=False)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.covariances is None

    def test_mismatched_object_name_raises(self):
        """Section 5.1.3 is now enforced at OEM construction; mismatched names never reach the converter."""
        import pydantic

        extra_seg = {
            "metadata_kwargs": {
                "object_name": "OTHER_SAT",
                "object_id": "2020-001A",
                "center_name": CenterName.EARTH,
                "ref_frame": RefFrame.GCRF,
                "time_system": TimeSystem.UTC,
                "start_time": "2020-001T12:00:00",
                "stop_time": "2020-001T13:00:00",
            },
            "ephemeris_data_lines": [
                {
                    "epoch": "2020-001T12:00:00",
                    "x": 6500.0,
                    "y": 0.0,
                    "z": 0.0,
                    "x_dot": 0.0,
                    "y_dot": 7.8,
                    "z_dot": 0.0,
                },
                {
                    "epoch": "2020-001T13:00:00",
                    "x": 6400.0,
                    "y": 0.0,
                    "z": 0.0,
                    "x_dot": 0.0,
                    "y_dot": 7.9,
                    "z_dot": 0.0,
                },
            ],
        }
        with pytest.raises(pydantic.ValidationError, match="OBJECT_NAME"):
            _make_oem(extra_segments=[extra_seg])

    def test_mismatched_object_id_raises(self):
        """Section 5.1.3 is now enforced at OEM construction; mismatched IDs never reach the converter."""
        import pydantic

        extra_seg = {
            "metadata_kwargs": {
                "object_name": "SAT",
                "object_id": "2020-002B",
                "center_name": CenterName.EARTH,
                "ref_frame": RefFrame.GCRF,
                "time_system": TimeSystem.UTC,
                "start_time": "2020-001T12:00:00",
                "stop_time": "2020-001T13:00:00",
            },
            "ephemeris_data_lines": [
                {
                    "epoch": "2020-001T12:00:00",
                    "x": 6500.0,
                    "y": 0.0,
                    "z": 0.0,
                    "x_dot": 0.0,
                    "y_dot": 7.8,
                    "z_dot": 0.0,
                },
                {
                    "epoch": "2020-001T13:00:00",
                    "x": 6400.0,
                    "y": 0.0,
                    "z": 0.0,
                    "x_dot": 0.0,
                    "y_dot": 7.9,
                    "z_dot": 0.0,
                },
            ],
        }
        with pytest.raises(pydantic.ValidationError, match="OBJECT_ID"):
            _make_oem(extra_segments=[extra_seg])

    def test_traj_id_auto_assigned_sequentially(self):
        extra_lines = [
            {"epoch": f"2020-001T{12 + i:02d}:00:00", **_BASE_EPH} for i in range(12)
        ]
        extra_seg = {
            "metadata_kwargs": {
                "object_name": "SAT",
                "object_id": "2020-001A",
                "center_name": CenterName.EARTH,
                "ref_frame": RefFrame.EME2000,
                "time_system": TimeSystem.UTC,
                "start_time": "2020-001T12:00:00",
                "stop_time": "2020-001T23:00:00",
            },
            "ephemeris_data_lines": extra_lines,
        }
        oem = _make_oem(extra_segments=[extra_seg])
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.trajectory_states[0].traj_id == "1"
        assert ocm.trajectory_states[1].traj_id == "2"

    def test_traj_units_cartpv(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.trajectory_states[0].traj_units == "[km,km,km,km/s,km/s,km/s]"

    def test_traj_units_cartpva(self):
        oem = _make_oem(with_accel=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert (
            ocm.trajectory_states[0].traj_units
            == "[km,km,km,km/s,km/s,km/s,km/s**2,km/s**2,km/s**2]"
        )

    def test_ocm_data_elements_orb_only(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.metadata.ocm_data_elements == "ORB"

    def test_ocm_data_elements_orb_and_cov(self):
        oem = _make_oem(with_covariance=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.metadata.ocm_data_elements == "ORB, COV"

    def test_traj_basis_forwarded(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.trajectory_states[0].traj_basis == "OPERATIONAL"

    def test_required_metadata_fields_present(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(
            oem,
            traj_basis="OPERATIONAL",
            object_designator="12345",
            operator="MY_OP",
            owner="MY_OWNER",
            country="USA",
            originator_address="123 Main St",
            originator_email="ops@example.com",
            originator_phone="+1-555-0100",
            message_id="MSG-001",
        )
        assert ocm.metadata.object_designator == "12345"
        assert ocm.metadata.operator == "MY_OP"
        assert ocm.metadata.owner == "MY_OWNER"
        assert ocm.metadata.country == "USA"
        assert ocm.metadata.originator_address == "123 Main St"
        assert ocm.metadata.originator_email == "ops@example.com"
        assert ocm.metadata.originator_phone == "+1-555-0100"

    def test_message_id_from_kwarg(self):
        oem = _make_oem()
        ocm = oem_to_tracss_ocm(oem, **{**TRACSS_REQUIRED, "message_id": "EXPLICIT-ID"})
        assert ocm.header.message_id == "EXPLICIT-ID"

    def test_message_id_falls_back_to_oem_header(self):
        oem = (
            OEM.builder()
            .header(
                originator="TEST_ORG",
                creation_date=CREATION_DATE,
                message_id="OEM-MSG-001",
            )
            .add_segment(
                metadata_kwargs={
                    "object_name": "SAT",
                    "object_id": "2020-001A",
                    "center_name": CenterName.EARTH,
                    "ref_frame": RefFrame.EME2000,
                    "time_system": TimeSystem.UTC,
                    "start_time": "2020-001T00:00:00",
                    "stop_time": "2020-001T11:00:00",
                },
                ephemeris_data_lines=[
                    {"epoch": f"2020-001T{i:02d}:00:00", **_BASE_EPH} for i in range(12)
                ],
            )
            .build()
        )
        # No message_id kwarg - falls back to OEM header's message_id.
        kwargs_without_msg_id = {
            k: v for k, v in TRACSS_REQUIRED.items() if k != "message_id"
        }
        ocm = oem_to_tracss_ocm(oem, **kwargs_without_msg_id)
        assert ocm.header.message_id == "OEM-MSG-001"

    def test_useable_record_padding_sets_useable_times(self):
        lines = [{"epoch": f"2020-001T{h:02d}:00:00", **_BASE_EPH} for h in range(12)]
        oem = (
            OEM.builder()
            .header(originator="TEST_ORG", creation_date=CREATION_DATE)
            .add_segment(
                metadata_kwargs={
                    "object_name": "SAT",
                    "object_id": "2020-001A",
                    "center_name": CenterName.EARTH,
                    "ref_frame": RefFrame.EME2000,
                    "time_system": TimeSystem.UTC,
                    "start_time": "2020-001T00:00:00",
                    "stop_time": "2020-001T11:00:00",
                },
                ephemeris_data_lines=lines,
            )
            .build()
        )
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED, useable_record_padding=5)
        traj = ocm.trajectory_states[0]
        assert traj.useable_start_time == "2020-001T05:00:00"
        assert traj.useable_stop_time == "2020-001T06:00:00"
        assert ocm.metadata.start_time == "2020-001T05:00:00"
        assert ocm.metadata.stop_time == "2020-001T06:00:00"

    def test_covariance_frame_mapping(self):
        # OEM covariance frames don't map one-to-one to the frames TraCSS accepts
        # (table 6: RSW_INERTIAL, TNW_INERTIAL). RSW and RTN are the same frame under two
        # names, so both map to RSW_INERTIAL; TNW maps to TNW_INERTIAL.
        # Each case uses three segments (2020-001 00-11h, 2020-001 12-23h, 2020-002
        # 00-11h) with the same OEM frame, so COV_ID numbering across segments is
        # checked too.
        for oem_frame, expected_ocm_frame in [
            ("RSW", "RSW_INERTIAL"),
            ("RTN", "RSW_INERTIAL"),
            ("TNW", "TNW_INERTIAL"),
        ]:
            oem = _make_multi_segment_oem(
                _make_segment("001", 0, cov_ref_frames=oem_frame),
                _make_segment("001", 12, cov_ref_frames=oem_frame),
                _make_segment("002", 0, cov_ref_frames=oem_frame),
            )
            ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
            assert ocm.covariances is not None
            assert [(c.cov_id, str(c.cov_ref_frame)) for c in ocm.covariances] == [
                ("1", expected_ocm_frame),
                ("2", expected_ocm_frame),
                ("3", expected_ocm_frame),
            ], f"OEM {oem_frame} should map to {expected_ocm_frame}"

    def test_covariance_frame_mapping_raises_on_unmapped_frame(self):
        # Covariance frames that are not in COV_REF_FRAME_MAPPING can't be expressed in a
        # TraCSS frame (table 6: RSW_INERTIAL, TNW_INERTIAL) and must raise, whether the
        # frame is set explicitly on the line or inherited from the segment REF_FRAME.
        for cov_ref_frames, expected_source in [
            ("EME2000", "from its COV_REF_FRAME"),
            ("GCRF", "from its COV_REF_FRAME"),
            ("RSW_ROTATING", "from its COV_REF_FRAME"),
            (None, "from the segment REF_FRAME"),  # falls back to EME2000
        ]:
            oem = _make_multi_segment_oem(
                _make_segment("001", 0, cov_ref_frames=cov_ref_frames)
            )
            with pytest.raises(ValueError) as exc_info:
                oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
            message = str(exc_info.value)
            expected_frame = cov_ref_frames or "EME2000"
            assert f"uses frame '{expected_frame}' {expected_source}" in message
            assert "Segment 0 covariance line 0 (epoch 2020-001T00:00:00)" in message
            assert "RSW_INERTIAL or TNW_INERTIAL" in message
            assert "RTN -> RSW_INERTIAL" in message  # lists the supported frames

    def test_covariance_frames_mapping_to_same_frame_share_one_block(self):
        # RSW and RTN lines in one segment both map to RSW_INERTIAL: one block, not two.
        frames = ["RSW", "RTN"] * 6
        oem = _make_multi_segment_oem(_make_segment("001", 0, cov_ref_frames=frames))
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.covariances is not None
        assert len(ocm.covariances) == 1
        assert str(ocm.covariances[0].cov_ref_frame) == "RSW_INERTIAL"
        assert len(ocm.covariances[0].data_lines) == 12

    # ---------------------------------------------------------------------------
    # TraCSS-specific validation
    # ---------------------------------------------------------------------------

    def test_raises_on_invalid_traj_basis(self):
        oem = _make_oem()
        with pytest.raises(ValueError, match="OPERATIONAL"):
            oem_to_tracss_ocm(oem, **{**TRACSS_REQUIRED, "traj_basis": "PROVISIONAL"})

    def test_raises_on_non_earth_center_name(self):
        oem = (
            OEM.builder()
            .header(originator="TEST_ORG", creation_date=CREATION_DATE)
            .add_segment(
                metadata_kwargs={
                    "object_name": "SAT",
                    "object_id": "2020-001A",
                    "center_name": CenterName.MOON,
                    "ref_frame": RefFrame.EME2000,
                    "time_system": TimeSystem.UTC,
                    "start_time": "2020-001T00:00:00",
                    "stop_time": "2020-001T11:00:00",
                },
                ephemeris_data_lines=[
                    {"epoch": f"2020-001T{i:02d}:00:00", **_BASE_EPH} for i in range(12)
                ],
            )
            .build()
        )
        with pytest.raises(ValueError, match="CENTER_NAME"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_raises_on_non_eme2000_ref_frame(self):
        oem = (
            OEM.builder()
            .header(originator="TEST_ORG", creation_date=CREATION_DATE)
            .add_segment(
                metadata_kwargs={
                    "object_name": "SAT",
                    "object_id": "2020-001A",
                    "center_name": CenterName.EARTH,
                    "ref_frame": RefFrame.GCRF,
                    "time_system": TimeSystem.UTC,
                    "start_time": "2020-001T00:00:00",
                    "stop_time": "2020-001T11:00:00",
                },
                ephemeris_data_lines=[
                    {"epoch": f"2020-001T{i:02d}:00:00", **_BASE_EPH} for i in range(12)
                ],
            )
            .build()
        )
        with pytest.raises(ValueError, match="EME2000"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_raises_on_missing_message_id(self):
        oem = _make_oem()  # no message_id in OEM header
        kwargs_without_msg_id = {
            k: v for k, v in TRACSS_REQUIRED.items() if k != "message_id"
        }
        with pytest.raises(ValueError, match="MESSAGE_ID"):
            oem_to_tracss_ocm(oem, **kwargs_without_msg_id)

    def test_raises_on_too_few_records_for_padding(self):
        oem = _make_oem(n_lines=3)  # 3 lines, needs >=11 for padding=5
        with pytest.raises(ValueError, match="USEABLE"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    # TraCSS-Spec-002 table 1 / section 7: orbit and covariance data pairing.

    def test_failure_only_one_segment_has_covariance_data(self):
        # Only segment 0 has covariance: TraCSS needs one covariance section per orbit
        # data section, so segment 1's orbit data would be left without one.
        oem = _make_multi_segment_oem(
            _make_segment("001", 0),
            _make_segment("001", 12, with_covariance=False),
        )
        with pytest.raises(
            ValueError, match="one covariance section per orbit data section"
        ):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_failure_segment_has_not_enough_covariance_data(self):
        # 12 ephemeris lines but only 3 covariance lines (at matching epochs).
        oem = _make_multi_segment_oem(
            _make_segment(
                "001",
                0,
                cov_epochs=[
                    "2020-001T00:00:00",
                    "2020-001T01:00:00",
                    "2020-001T02:00:00",
                ],
            ),
        )
        with pytest.raises(ValueError, match="one covariance line per orbit data line"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_failure_covariance_epochs_do_not_match_ephemeris(self):
        # Same number of lines, but the 6th covariance epoch is 05:30 instead of 05:00
        # (OEM itself already rejects covariance epochs outside the segment span).
        cov_epochs = [f"2020-001T{i:02d}:00:00" for i in range(12)]
        cov_epochs[5] = "2020-001T05:30:00"
        oem = _make_multi_segment_oem(_make_segment("001", 0, cov_epochs=cov_epochs))
        with pytest.raises(ValueError, match="identical epochs"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_failure_segments_have_different_trajectory_frame(self):
        oem = _make_multi_segment_oem(
            _make_segment("001", 0, ref_frame=RefFrame.EME2000),
            _make_segment("001", 12, ref_frame=RefFrame.GCRF),
        )
        with pytest.raises(ValueError, match="EME2000"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_failure_segments_have_different_covariance_frame(self):
        oem = _make_multi_segment_oem(
            _make_segment("001", 0, cov_ref_frames="RSW"),
            _make_segment("001", 12, cov_ref_frames="TNW"),
        )
        with pytest.raises(ValueError, match="same covariance frame"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)

    def test_failure_segment_has_mixed_covariance_frames(self):
        # RTN and TNW map to different OCM frames, which one covariance section can't hold.
        frames = ["RTN", "TNW"] * 6
        oem = _make_multi_segment_oem(_make_segment("001", 0, cov_ref_frames=frames))
        with pytest.raises(ValueError, match="mixes covariance frames"):
            oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
