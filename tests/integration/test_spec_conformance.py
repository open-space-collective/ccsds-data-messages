"""
Spec conformance tests - anchored to CCSDS 502.0-B-3 section numbers.

These tests document what the spec requires and fail when the code diverges.
Some tests are expected to fail today (gaps confirmed at runtime); they are
marked with a comment # GAP so they are easy to grep.

Do NOT add xfail to gap tests.  Failing tests are the signal.
"""

from __future__ import annotations

import pydantic
import pytest
from conftest import CREATION_DATE
from conftest import EPOCH
from conftest import FIXTURES
from conftest import make_oem

from ccsds_data_messages import OCM
from ccsds_data_messages import OEM
from ccsds_data_messages import OMM
from ccsds_data_messages import OPM
from ccsds_data_messages import read
from ccsds_data_messages.io.kvn.ocm_writer import KVNOCMWriter
from ccsds_data_messages.io.kvn.oem_writer import KVNOEMWriter
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import Interpolation
from ccsds_data_messages.models.values import MeanElementTheory
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

_HEADER_KW = {"creation_date": CREATION_DATE, "originator": "TEST"}


# ---------------------------------------------------------------------------
# Section 7.7  Units in KVN output
# ---------------------------------------------------------------------------


class TestSection77KvnUnits:
    """
    Section 7.7 Units in Orbit Data Messages - KVN format.

    Section 7.7.2.1: OEM ephemeris data lines - "units shall not be displayed."
    Section 7.7.2.2: OEM covariance data lines - "units shall not be displayed."
    Section 7.7.3.5: OCM trajectory/covariance/maneuver data lines - "Units shall
              not be displayed in OCM trajectory state, covariance, or
              maneuver data lines themselves."
    """

    def _data_lines_from_kvn(self, text: str) -> list[str]:
        """Return lines from KVN output that look like numeric data (epoch-prefixed or all-numeric)."""
        import re

        result = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Skip keyword=value lines, block markers, and comment lines
            if "=" in stripped or stripped.startswith("COMMENT"):
                continue
            if re.match(r"^[A-Z_]+(START|STOP)$", stripped):
                continue
            # Must start with a digit or sign (data lines or bare numeric lines)
            if re.match(r"^[\d+-]", stripped):
                result.append(stripped)
        return result

    def test_oem_kvn_ephemeris_data_lines_have_no_inline_units_when_include_units_false(
        self,
    ):
        """Section 7.7.2.1: With include_units=False, ephemeris lines have no [unit] annotations."""
        oem = make_oem(n_lines=3)
        writer = KVNOEMWriter()
        output = writer.write_string(oem, options=WriterOptions(include_units=False))
        data_lines = self._data_lines_from_kvn(output)
        assert data_lines, "Expected at least one data line in OEM KVN output"
        for line in data_lines:
            assert "[" not in line, (
                f"section 7.7.2.1: inline unit found in OEM ephemeris line (include_units=False): {line!r}"
            )

    def test_oem_kvn_ephemeris_data_lines_have_no_inline_units_when_include_units_true(
        self,
    ):
        """Section 7.7.2.1: Even with include_units=True, OEM KVN ephemeris lines must not carry units."""
        oem = make_oem(n_lines=3)
        writer = KVNOEMWriter()
        output = writer.write_string(oem, options=WriterOptions(include_units=True))
        data_lines = self._data_lines_from_kvn(output)
        assert data_lines, "Expected at least one data line in OEM KVN output"
        for line in data_lines:
            assert "[" not in line, (
                f"section 7.7.2.1: inline unit found in OEM ephemeris line (include_units=True): {line!r}"
            )

    def test_oem_kvn_covariance_data_lines_have_no_inline_units(self):
        """Section 7.7.2.2: OEM KVN covariance data lines must not display units."""
        oem = read(FIXTURES / "oem_g13_covariance.kvn", fmt="kvn", message_type="oem")
        writer = KVNOEMWriter()
        output = writer.write_string(oem, options=WriterOptions(include_units=True))

        in_covariance = False
        for line in output.splitlines():
            stripped = line.strip()
            if stripped == "COVARIANCE_START":
                in_covariance = True
                continue
            if stripped == "COVARIANCE_STOP":
                in_covariance = False
                continue
            if (
                in_covariance
                and stripped
                and "=" not in stripped
                and not stripped.startswith("COMMENT")
            ):
                assert "[" not in stripped, (
                    f"section 7.7.2.2: inline unit in OEM KVN covariance data line: {stripped!r}"
                )

    def test_ocm_kvn_trajectory_data_lines_have_no_inline_units(self):
        """Section 7.7.3.5: OCM KVN trajectory data lines must not carry inline units."""
        ocm = OCM(
            header=OCM.Header(ccsds_ocm_vers="3.0", **_HEADER_KW),
            metadata=OCM.Metadata(time_system=TimeSystem.UTC, epoch_tzero=EPOCH),
            trajectory_states=[
                OCM.TrajectoryStateTimeHistory(
                    traj_type="CARTPV",
                    traj_id="PLAN",
                    data_lines=[
                        "2020-001T00:00:00 7000.0 0.0 0.0 0.0 7.5 0.0",
                        "2020-001T00:10:00 6990.0 0.0 0.0 0.0 7.5 0.0",
                    ],
                )
            ],
        )
        writer = KVNOCMWriter()
        output = writer.write_string(ocm, options=WriterOptions(include_units=True))
        for line in output.splitlines():
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and "T" in stripped.split()[0]:
                assert "[" not in stripped, (
                    f"section 7.7.3.5: inline unit in OCM KVN trajectory data line: {stripped!r}"
                )

    def test_kvn_parser_strips_inline_unit_from_key_value_line(self):
        """Section 7.7.1.1: KVN parser must strip the optional [unit] suffix, not include it in value."""
        from ccsds_data_messages.io.kvn.parser import KeyValueLine
        from ccsds_data_messages.io.kvn.parser import parse_kvn

        lines = list(parse_kvn("X = 7000.000 [km]"))
        kv_lines = [line for line in lines if isinstance(line, KeyValueLine)]
        assert kv_lines, "Expected a KeyValueLine"
        kv = kv_lines[0]
        assert kv.keyword == "X"
        # Value must be the numeric string only, not including "[km]"
        assert "[" not in kv.value, f"Parser left unit annotation in value: {kv.value!r}"
        assert kv.value.strip() == "7000.000"

    def test_kvn_parser_value_is_correct_after_unit_strip(self):
        """Section 7.7.1.1: Value parsed from 'X = -1234.5 [km]' is exactly '-1234.5'."""
        from ccsds_data_messages.io.kvn.parser import KeyValueLine
        from ccsds_data_messages.io.kvn.parser import parse_kvn

        lines = list(parse_kvn("X = -1234.5 [km]"))
        kv_lines = [line for line in lines if isinstance(line, KeyValueLine)]
        assert kv_lines
        assert kv_lines[0].value.strip() == "-1234.5"


# ---------------------------------------------------------------------------
# Section 7.9.1  Valid version strings per message type
# ---------------------------------------------------------------------------


class TestSection791ValidVersions:
    """
    Section 7.9.1 - valid version strings per message type.

    OPM: 1.0, 2.0, 3.0
    OMM: 2.0, 3.0
    OEM: 1.0, 2.0, 3.0
    OCM: 3.X (major must be 3)

    Current state: VersionStr uses r"3\\.\\d+" - OPM 1.0/2.0 and OMM 2.0
    are wrongly rejected. Tests below document the correct spec behavior.
    """

    # --- OPM ---

    @pytest.mark.parametrize("vers", ["3.0"])
    def test_opm_version_3_x_accepted(self, vers: str):
        """OPM versions in {1.0, 2.0, 3.0} must all construct. (section 7.9.1)"""
        h = OPM.Header(ccsds_opm_vers=vers, **_HEADER_KW)
        assert h.ccsds_opm_vers == vers

    @pytest.mark.parametrize("vers", ["1.0", "2.0"])
    def test_opm_version_in_valid_set_accepted(self, vers: str):
        """
        Section 7.9.1 lists OPM versions as {1.0, 2.0, 3.0}; any of these must construct.

        GAP: current VersionStr validator pattern r'3\\.\\d+' wrongly rejects 1.0 and 2.0.
        """
        # GAP - will fail until VersionStr is per-message-type
        h = OPM.Header(ccsds_opm_vers=vers, **_HEADER_KW)
        assert h.ccsds_opm_vers == vers

    def test_opm_version_4_0_raises_outside_valid_set(self):
        """Section 7.9.1: '4.0' is not a valid OPM version; must raise ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            OPM.Header(ccsds_opm_vers="4.0", **_HEADER_KW)

    def test_opm_version_non_numeric_raises(self):
        """Section 7.9.1: non-numeric version strings must raise ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            OPM.Header(ccsds_opm_vers="abc", **_HEADER_KW)

    # --- OMM ---

    def test_omm_version_3_0_accepted(self):
        """OMM v3.0 must construct."""
        h = OMM.Header(ccsds_omm_vers="3.0", **_HEADER_KW)
        assert h.ccsds_omm_vers == "3.0"

    def test_omm_version_2_0_is_valid_per_spec(self):
        """
        Section 7.9.1 lists OMM versions as {2.0, 3.0}; v2.0 must construct.

        GAP: current VersionStr wrongly rejects 2.0.
        """
        # GAP - will fail until VersionStr is per-message-type
        h = OMM.Header(ccsds_omm_vers="2.0", **_HEADER_KW)
        assert h.ccsds_omm_vers == "2.0"

    def test_omm_version_1_0_raises_not_in_valid_set(self):
        """Section 7.9.1: OMM has no version 1.0; must raise ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            OMM.Header(ccsds_omm_vers="1.0", **_HEADER_KW)

    def test_omm_version_4_0_raises_outside_valid_set(self):
        """Section 7.9.1: '4.0' is not a valid OMM version; must raise ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            OMM.Header(ccsds_omm_vers="4.0", **_HEADER_KW)

    # --- OEM ---

    def test_oem_version_3_0_accepted(self):
        """OEM v3.0 must construct."""
        h = OEM.Header(ccsds_oem_vers="3.0", **_HEADER_KW)
        assert h.ccsds_oem_vers == "3.0"

    @pytest.mark.parametrize("vers", ["1.0", "2.0"])
    def test_oem_version_in_valid_set_accepted(self, vers: str):
        """
        Section 7.9.1 lists OEM versions as {1.0, 2.0, 3.0}; any must construct.

        GAP: current VersionStr wrongly rejects 1.0 and 2.0.
        """
        # GAP - will fail until VersionStr is per-message-type
        h = OEM.Header(ccsds_oem_vers=vers, **_HEADER_KW)
        assert h.ccsds_oem_vers == vers

    def test_oem_version_4_0_raises_outside_valid_set(self):
        """Section 7.9.1: '4.0' is not a valid OEM version; must raise ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            OEM.Header(ccsds_oem_vers="4.0", **_HEADER_KW)

    # --- OCM ---

    @pytest.mark.parametrize("vers", ["3.0", "3.1", "3.5"])
    def test_ocm_version_3_x_accepted(self, vers: str):
        """Section 7.9.1: any OCM version with major=3 must construct."""
        h = OCM.Header(ccsds_ocm_vers=vers, **_HEADER_KW)
        assert h.ccsds_ocm_vers == vers

    def test_ocm_version_4_0_raises_non_3_major(self):
        """Section 7.9.1: OCM major version must be 3; '4.0' must raise."""
        with pytest.raises(pydantic.ValidationError):
            OCM.Header(ccsds_ocm_vers="4.0", **_HEADER_KW)

    def test_ocm_version_2_0_raises_non_3_major(self):
        """Section 7.9.1: OCM major version must be 3; '2.0' must raise."""
        with pytest.raises(pydantic.ValidationError):
            OCM.Header(ccsds_ocm_vers="2.0", **_HEADER_KW)


# ---------------------------------------------------------------------------
# Section 5.1.3  OEM single-object constraint
# ---------------------------------------------------------------------------


class TestSection513OEMSingleObject:
    """Section 5.1.3 - 'The OEM shall be a plain text file consisting of orbit data for a single object.'"""

    def _make_segment(self, object_name: str, epoch_offset: int = 0) -> OEM.Segment:
        start = f"2020-001T{epoch_offset:02d}:00:00"
        stop = f"2020-001T{epoch_offset + 1:02d}:00:00"
        return OEM.Segment(
            metadata=OEM.Segment.Metadata(
                object_name=object_name,
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.EME2000,
                time_system=TimeSystem.UTC,
                start_time=start,
                stop_time=stop,
            ),
            ephemeris_data=OEM.Segment.EphemerisData(
                ephemeris_data_lines=[
                    OEM.Segment.EphemerisData.EphemerisDataLine(
                        epoch=start,
                        x=7000.0,
                        y=0.0,
                        z=0.0,
                        x_dot=0.0,
                        y_dot=7.5,
                        z_dot=0.0,
                    )
                ],
            ),
        )

    def test_oem_segments_with_same_object_name_accepted(self):
        """Two segments for the same object must construct without error."""
        oem = OEM(
            header=OEM.Header(ccsds_oem_vers="3.0", **_HEADER_KW),
            segments=[
                self._make_segment("SAT_A", epoch_offset=0),
                self._make_segment("SAT_A", epoch_offset=1),
            ],
        )
        assert len(oem.segments) == 2
        assert (
            oem.segments[0].metadata.object_name == oem.segments[1].metadata.object_name
        )

    def test_oem_segments_with_different_object_names_raises_validation_error(self):
        """Section 5.1.3: segments with different OBJECT_NAME values violate the single-object rule."""
        with pytest.raises(pydantic.ValidationError, match="OBJECT_NAME"):
            OEM(
                header=OEM.Header(ccsds_oem_vers="3.0", **_HEADER_KW),
                segments=[
                    self._make_segment("SAT_A", epoch_offset=0),
                    self._make_segment("SAT_B", epoch_offset=1),  # different object
                ],
            )


# ---------------------------------------------------------------------------
# Section 5.2.4.7  OEM interpolation - sufficient ephemeris records
# ---------------------------------------------------------------------------


class TestSection5247InterpolationRecords:
    """
    Section 5.2.4.7 - data blocks must contain enough ephemeris records for interpolation.

    Rule: len(ephemeris_data_lines) >= interpolation_degree + 1
    """

    def _make_oem_with_interpolation(
        self,
        method: Interpolation,
        degree: int,
        n_lines: int,
    ) -> OEM:
        epochs = [f"2020-001T00:{i * 10:02d}:00" for i in range(max(n_lines, 2))]
        actual_epochs = epochs[:n_lines]
        return OEM(
            header=OEM.Header(ccsds_oem_vers="3.0", **_HEADER_KW),
            segments=[
                OEM.Segment(
                    metadata=OEM.Segment.Metadata(
                        object_name="TESTSAT",
                        object_id="2020-001A",
                        center_name=CenterName.EARTH,
                        ref_frame=RefFrame.EME2000,
                        time_system=TimeSystem.UTC,
                        start_time=epochs[0],
                        stop_time=epochs[-1],
                        interpolation=method,
                        interpolation_degree=degree,
                    ),
                    ephemeris_data=OEM.Segment.EphemerisData(
                        ephemeris_data_lines=[
                            OEM.Segment.EphemerisData.EphemerisDataLine(
                                epoch=actual_epochs[i],
                                x=7000.0 - i * 10,
                                y=0.0,
                                z=0.0,
                                x_dot=0.0,
                                y_dot=7.5,
                                z_dot=0.0,
                            )
                            for i in range(n_lines)
                        ],
                    ),
                )
            ],
        )

    def test_lagrange_degree_3_with_4_data_lines_accepted(self):
        """LAGRANGE degree=3 needs >= 4 records; exactly 4 must be accepted."""
        oem = self._make_oem_with_interpolation(Interpolation.LAGRANGE, 3, 4)
        assert len(oem.segments[0].ephemeris_data.ephemeris_data_lines) == 4

    def test_lagrange_degree_5_with_2_data_lines_raises_validation_error(self):
        """Section 5.2.4.7: LAGRANGE degree=5 requires >= 6 records; only 2 must raise."""
        with pytest.raises(pydantic.ValidationError, match="ephemeris data records"):
            self._make_oem_with_interpolation(Interpolation.LAGRANGE, 5, 2)

    def test_lagrange_degree_5_with_6_data_lines_accepted(self):
        """LAGRANGE degree=5 needs >= 6 records; exactly 6 must be accepted."""
        oem = self._make_oem_with_interpolation(Interpolation.LAGRANGE, 5, 6)
        assert len(oem.segments[0].ephemeris_data.ephemeris_data_lines) == 6

    def test_linear_interpolation_with_1_data_line_raises_validation_error(self):
        """Section 5.2.4.7: LINEAR requires >= 2 records to interpolate; 1 line must raise."""
        with pytest.raises(pydantic.ValidationError, match="ephemeris data records"):
            OEM(
                header=OEM.Header(ccsds_oem_vers="3.0", **_HEADER_KW),
                segments=[
                    OEM.Segment(
                        metadata=OEM.Segment.Metadata(
                            object_name="TESTSAT",
                            object_id="2020-001A",
                            center_name=CenterName.EARTH,
                            ref_frame=RefFrame.EME2000,
                            time_system=TimeSystem.UTC,
                            start_time="2020-001T00:00:00",
                            stop_time="2020-001T01:00:00",
                            interpolation=Interpolation.LINEAR,
                            interpolation_degree=1,
                        ),
                        ephemeris_data=OEM.Segment.EphemerisData(
                            ephemeris_data_lines=[
                                OEM.Segment.EphemerisData.EphemerisDataLine(
                                    epoch="2020-001T00:00:00",
                                    x=7000.0,
                                    y=0.0,
                                    z=0.0,
                                    x_dot=0.0,
                                    y_dot=7.5,
                                    z_dot=0.0,
                                )
                            ],
                        ),
                    )
                ],
            )


# ---------------------------------------------------------------------------
# Section 4.2.4.6  OMM TLE-based conventions - forward direction
# ---------------------------------------------------------------------------


class TestSection4246OMMSGP4:
    """
    Section 4.2.4.6 - TLE-based OMMs: CENTER_NAME=EARTH, REF_FRAME=TEME, TIME_SYSTEM=UTC.

    ``validate_tle_theory_requires_teme`` enforces the forward direction
    (SGP/SGP4 theory -> REF_FRAME=TEME); ``validate_teme_constraints`` enforces
    the reverse (REF_FRAME=TEME -> EARTH + UTC).
    """

    def _make_sgp4_omm(
        self, ref_frame: RefFrame, center: CenterName = CenterName.EARTH
    ) -> OMM:
        return OMM(
            header=OMM.Header(ccsds_omm_vers="3.0", **_HEADER_KW),
            metadata=OMM.Metadata(
                object_name="TESTSAT",
                object_id="1999-025A",
                center_name=center,
                ref_frame=ref_frame,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.SGP4,
            ),
            data=OMM.Data(
                mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                    epoch=EPOCH,
                    inclination=51.6,
                    ra_of_asc_node=120.0,
                    eccentricity=0.001,
                    arg_of_pericenter=30.0,
                    mean_anomaly=45.0,
                    mean_motion=15.2,  # SGP4 uses mean_motion
                ),
                tle_related_parameters=OMM.Data.TLERelatedParameters(
                    norad_cat_id=25544,
                    bstar=2.8098e-5,
                    mean_motion_dot=6.969196e-13,
                    mean_motion_ddot=0.0,
                    element_set_no=292,
                    rev_at_epoch=6766,
                ),
            ),
        )

    def test_sgp4_theory_with_teme_frame_and_earth_center_accepted(self):
        """Section 4.2.4.6 happy path: SGP4 + TEME + EARTH + UTC must construct."""
        omm = self._make_sgp4_omm(ref_frame=RefFrame.TEME)
        assert omm.metadata.mean_element_theory == MeanElementTheory.SGP4
        assert omm.metadata.ref_frame == RefFrame.TEME

    def test_sgp4_theory_with_eme2000_frame_raises_validation_error(self):
        """Section 4.2.4.6: SGP4 requires REF_FRAME=TEME; EME2000 must raise ValidationError."""
        with pytest.raises(pydantic.ValidationError, match="requires REF_FRAME=TEME"):
            self._make_sgp4_omm(ref_frame=RefFrame.EME2000)

    def test_sgp4_theory_with_gcrf_frame_raises_validation_error(self):
        """Section 4.2.4.6: SGP4 requires REF_FRAME=TEME; GCRF must also raise ValidationError."""
        with pytest.raises(pydantic.ValidationError, match="requires REF_FRAME=TEME"):
            self._make_sgp4_omm(ref_frame=RefFrame.GCRF)
