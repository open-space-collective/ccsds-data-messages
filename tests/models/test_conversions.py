"""
OEM-to-TraCSS-OCM conversion tests.

Module under test: src/ccsds_data_messages/models/conversions.py (oem_to_tracss_ocm)
"""

from __future__ import annotations

import pytest

from ccsds_data_messages import OEM
from ccsds_data_messages import oem_to_tracss_ocm
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import ManCovRefFrame
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
    (needs >=11 lines). Uses EME2000 as required by TraCSS.
    """
    base_line: dict = dict(**_BASE_EPH)
    if with_accel:
        base_line.update(x_ddot=0.001, y_ddot=0.002, z_ddot=0.003)

    lines = [{"epoch": f"2020-001T{i:02d}:00:00", **base_line} for i in range(n_lines)]

    cov_lines = None
    if with_covariance:
        cov_lines = [
            {"epoch": f"2020-001T{i:02d}:00:00", **_COV_LINE_BASE} for i in range(n_lines)
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
        assert traj.center_name == CenterName.EARTH
        assert traj.traj_ref_frame == RefFrame.EME2000

    def test_covariance_block_produced_when_cov_present(self):
        oem = _make_oem(with_covariance=True)
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.covariances is not None
        assert len(ocm.covariances) == 1
        cov = ocm.covariances[0]
        assert cov.cov_type == OrbitalElements.CARTPV
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

    def test_mixed_cov_ref_frame_splits_into_multiple_blocks(self):
        # Two distinct cov_ref_frame values in one segment produce two CovarianceTimeHistory blocks.
        # Extra seg uses 12 ephem lines (EME2000) with 3 covariance lines (RTN, TNW, RTN).
        # Starts after the default segment's stop_time (11:00) - spans must not overlap (5.2.4.4).
        extra_ephem = [
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
            "ephemeris_data_lines": extra_ephem,
            "covariance_matrix_lines": [
                dict(
                    epoch="2020-001T12:00:00",
                    cov_ref_frame=ManCovRefFrame.RTN,
                    **_COV_LINE_BASE,
                ),
                dict(
                    epoch="2020-001T13:00:00",
                    cov_ref_frame=ManCovRefFrame.TNW,
                    **_COV_LINE_BASE,
                ),
                dict(
                    epoch="2020-001T14:00:00",
                    cov_ref_frame=ManCovRefFrame.RTN,
                    **_COV_LINE_BASE,
                ),
            ],
        }
        oem = _make_oem(with_covariance=False, extra_segments=[extra_seg])
        ocm = oem_to_tracss_ocm(oem, **TRACSS_REQUIRED)
        assert ocm.covariances is not None
        assert len(ocm.covariances) == 2
        frames = {str(b.cov_ref_frame) for b in ocm.covariances}
        assert frames == {"RTN", "TNW"}
        rtn_block = next(b for b in ocm.covariances if str(b.cov_ref_frame) == "RTN")
        tnw_block = next(b for b in ocm.covariances if str(b.cov_ref_frame) == "TNW")
        assert len(rtn_block.data_lines) == 2
        assert len(tnw_block.data_lines) == 1

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
