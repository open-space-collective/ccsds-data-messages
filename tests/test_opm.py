"""
OPM tests - model validation, spec fixtures (Annex G1-G5), KVN/XML round-trips.

Replaces:
- test_models.py:TestOPM, TestF1-F4, TestF2ManRefFrameWarning, TestOPMBuilder
- test_roundtrip.py:TestKVNRoundTrip.test_opm_*, TestXMLRoundTrip.test_opm_*,
  test_opm_maneuvers_valid_ref_frame
- test_spec_fixtures.py:opm_g1..g5 rows
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, ClassVar

import pydantic
import pytest
from conftest import (
    CREATION_DATE,
    EPOCH,
    FIXTURE_WRITE_OPTIONS,
    FIXTURES,
    assert_models_equal,
    assert_opm_equal,
    assert_semantic_equal,
    make_opm,
)

from ccsds_data_messages import OPM, read, write
from ccsds_data_messages.io.kvn.opm_reader import KVNOPMReader
from ccsds_data_messages.io.kvn.opm_writer import KVNOPMWriter
from ccsds_data_messages.models import SpacecraftParameters
from ccsds_data_messages.models._base import BaseCovarianceMatrix
from ccsds_data_messages.models.values import (
    CenterName,
    ManCovRefFrame,
    RefFrame,
    TimeSystem,
)

if TYPE_CHECKING:
    from pathlib import Path

_OPM_READER = KVNOPMReader()
_OPM_WRITER = KVNOPMWriter()

_OPM_SPEC_FIXTURES = [
    ("opm_g1_simple.kvn", "kvn"),
    ("opm_g2_maneuvers.kvn", "kvn"),
    ("opm_g3_covariance.kvn", "kvn"),
    ("opm_g4_keplerian_covariance.kvn", "kvn"),
    ("opm_g5.xml", "xml"),
]


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestOPMModel:
    def test_opm_minimal_construction_succeeds(self):
        # §3.2: all mandatory fields present => no exception
        opm = make_opm()
        assert opm.header.ccsds_opm_vers == "3.0"
        assert opm.metadata.object_name == "TESTSAT"
        assert opm.data.state_vector.x == 7000.0

    def test_opm_version_must_match_xy_pattern(self):
        # §7.9.1: version must be in 'x.y' form
        with pytest.raises(pydantic.ValidationError):
            OPM.Header(ccsds_opm_vers="3", creation_date=CREATION_DATE, originator="TEST")

    def test_opm_version_abc_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            OPM.Header(
                ccsds_opm_vers="abc", creation_date=CREATION_DATE, originator="TEST"
            )

    def test_opm_creation_date_must_be_valid_ccsds_epoch(self):
        # CREATION_DATE is Mandatory (§3.2.2, Table 3-1)
        with pytest.raises(pydantic.ValidationError):
            OPM.Header(
                ccsds_opm_vers="3.0", creation_date="not-a-date", originator="TEST"
            )

    def test_opm_object_name_mandatory(self):
        # Table 3-2 marks OBJECT_NAME M (§3.2.3)
        with pytest.raises(pydantic.ValidationError):
            OPM.Metadata(
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )

    def test_opm_center_name_mandatory(self):
        # Table 3-2 marks CENTER_NAME M
        with pytest.raises(pydantic.ValidationError):
            OPM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )

    def test_opm_ref_frame_mandatory(self):
        # Table 3-2 marks REF_FRAME M
        with pytest.raises(pydantic.ValidationError):
            OPM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                time_system=TimeSystem.UTC,
            )

    def test_opm_time_system_mandatory(self):
        # Table 3-2 marks TIME_SYSTEM M
        with pytest.raises(pydantic.ValidationError):
            OPM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
            )

    def test_opm_teme_ref_frame_rejected(self):
        # §3.2.3.3: TEME is "only used in OMMs"
        with pytest.raises(pydantic.ValidationError):
            OPM.Metadata(
                object_name="SAT",
                object_id="X",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.TEME,
                time_system=TimeSystem.UTC,
            )

    def test_opm_state_vector_x_mandatory(self):
        # Table 3-3 marks X M
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.StateVector(
                epoch=EPOCH, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
            )

    def test_opm_state_vector_y_dot_mandatory(self):
        # Table 3-3 marks Y_DOT M
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.StateVector(
                epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, z_dot=0.0
            )

    def test_opm_true_anomaly_and_mean_anomaly_mutually_exclusive(self):
        # Table 3-3 (C): TRUE_ANOMALY or MEAN_ANOMALY, not both
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.OsculatingKeplerianElements(
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                true_anomaly=10.0,
                mean_anomaly=10.0,
            )

    def test_opm_keplerian_block_requires_one_anomaly(self):
        # Exactly one of true_anomaly / mean_anomaly must be provided
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.OsculatingKeplerianElements(
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
            )

    def test_opm_maneuver_requires_mass(self):
        # §3.2.4.9: mass is mandatory when maneuver is present
        sv = OPM.Data.StateVector(
            epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
        )
        man = OPM.Data.ManeuverParameters(
            man_epoch_ignition=EPOCH, man_dv_1=0.001, man_dv_2=0.0, man_dv_3=0.0
        )
        with pytest.raises(pydantic.ValidationError):
            OPM.Data(state_vector=sv, maneuvers=[man])

    def test_opm_man_delta_mass_must_be_negative(self):
        # §3.2.4.7: MAN_DELTA_MASS "must be a negative number"
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.ManeuverParameters(man_delta_mass=0.0)

    def test_opm_man_delta_mass_positive_raises(self):
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.ManeuverParameters(man_delta_mass=1.0)

    def test_opm_comment_empty_list_raises(self):
        # Empty comment list is semantically invalid
        with pytest.raises(pydantic.ValidationError):
            OPM.Header(
                ccsds_opm_vers="3.0",
                creation_date=CREATION_DATE,
                originator="TEST",
                comment=[],
            )

    def test_opm_comment_non_empty_accepted(self):
        h = OPM.Header(
            ccsds_opm_vers="3.0",
            creation_date=CREATION_DATE,
            originator="TEST",
            comment=["Some note"],
        )
        assert h.comment == ["Some note"]

    def test_opm_man_ref_frame_narrow_normative_accepted(self):
        # §3.2.4.11: RSW, RTN, TNW are the preferred normative set
        mp = OPM.Data.ManeuverParameters(man_ref_frame=ManCovRefFrame.RTN)
        assert mp.man_ref_frame == ManCovRefFrame.RTN

    def test_opm_man_ref_frame_non_normative_warns(self):
        # Non-normative frame accepted with UserWarning; documented in §3.2.4.11
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            mp = OPM.Data.ManeuverParameters(man_ref_frame=RefFrame.EME2000)
        assert any(issubclass(warning.category, UserWarning) for warning in w)
        assert mp.man_ref_frame == RefFrame.EME2000

    def test_opm_man_ref_frame_normative_no_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            mp = OPM.Data.ManeuverParameters(man_ref_frame=ManCovRefFrame.RTN)
        assert mp.man_ref_frame == ManCovRefFrame.RTN

    def test_opm_spacecraft_parameters_is_shared_base(self):
        assert issubclass(OPM.Data.SpacecraftParameters, SpacecraftParameters)

    def test_opm_covariance_matrix_is_base_covariance(self):
        assert issubclass(OPM.Data.CovarianceMatrix, BaseCovarianceMatrix)

    def test_opm_user_defined_parameters_accepted(self):
        # §3.2.4.12: user-defined parameters with USER_DEFINED_x suffix
        udp = OPM.Data.UserDefinedParameters(user_defined={"EARTH_MODEL": "WGS-84"})
        assert udp.user_defined["EARTH_MODEL"] == "WGS-84"

    def test_opm_user_defined_empty_raises(self):
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.UserDefinedParameters(user_defined={})

    def test_opm_doy_epoch_format_accepted_in_state_vector(self):
        # §7.5.10: YYYY-DDDThh:mm:ss format is valid
        sv = OPM.Data.StateVector(
            epoch="2020-001T00:00:00",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
        )
        assert sv.epoch == "2020-001T00:00:00"

    def test_opm_julian_date_epoch_rejected(self):
        # epoch is absolute-only (CCSDSDate); §7.5.10 defines only the
        # calendar and day-of-year formats, so a bare decimal is rejected.
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.StateVector(
                epoch="2459945.5",
                x=7000.0,
                y=0.0,
                z=0.0,
                x_dot=0.0,
                y_dot=7.5,
                z_dot=0.0,
            )

    def test_opm_doy_400_epoch_rejected(self):
        # §7.5.10 / semantic range: DOY 400 is never valid
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.StateVector(
                epoch="2025-400T00:00:00",
                x=7000.0,
                y=0.0,
                z=0.0,
                x_dot=0.0,
                y_dot=7.5,
                z_dot=0.0,
            )

    def test_opm_doy_365_accepted_non_leap_year(self):
        sv = OPM.Data.StateVector(
            epoch="2025-365T00:00:00",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
        )
        assert sv.epoch == "2025-365T00:00:00"

    def test_opm_doy_366_accepted_leap_year(self):
        sv = OPM.Data.StateVector(
            epoch="2024-366T00:00:00",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
        )
        assert sv.epoch == "2024-366T00:00:00"

    def test_opm_doy_366_rejected_non_leap_year(self):
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.StateVector(
                epoch="2025-366T00:00:00",
                x=7000.0,
                y=0.0,
                z=0.0,
                x_dot=0.0,
                y_dot=7.5,
                z_dot=0.0,
            )

    def test_opm_calendar_month_13_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            OPM.Data.StateVector(
                epoch="2025-13-01T00:00:00",
                x=7000.0,
                y=0.0,
                z=0.0,
                x_dot=0.0,
                y_dot=7.5,
                z_dot=0.0,
            )


class TestOPMGmConditional:
    """F1: OPM.OsculatingKeplerianElements.gm is conditional on CENTER_NAME (§3.2.4.6)."""

    _KEP_KW: ClassVar[dict[str, float]] = {
        "semi_major_axis": 7000.0,
        "eccentricity": 0.001,
        "inclination": 51.6,
        "ra_of_asc_node": 0.0,
        "arg_of_pericenter": 0.0,
        "true_anomaly": 0.0,
    }

    def _opm_with_keplerian(self, center_name: CenterName, gm: float | None) -> OPM:
        return OPM(
            header=OPM.Header(
                ccsds_opm_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
            ),
            metadata=OPM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=center_name,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            ),
            data=OPM.Data(
                state_vector=OPM.Data.StateVector(
                    epoch=EPOCH,
                    x=7000.0,
                    y=0.0,
                    z=0.0,
                    x_dot=0.0,
                    y_dot=7.5,
                    z_dot=0.0,
                ),
                osculating_keplerian_elements=OPM.Data.OsculatingKeplerianElements(
                    **{**self._KEP_KW, "gm": gm}
                ),
            ),
        )

    def test_earth_center_gm_none_passes(self):
        opm = self._opm_with_keplerian(CenterName.EARTH, gm=None)
        assert opm.data.osculating_keplerian_elements.gm is None

    def test_earth_center_gm_provided_passes(self):
        opm = self._opm_with_keplerian(CenterName.EARTH, gm=398600.4418)
        assert opm.data.osculating_keplerian_elements.gm == 398600.4418

    def test_unknown_center_gm_none_raises(self):
        # CenterName.CHARON has no universally published GM
        with pytest.raises(pydantic.ValidationError, match="GM is required"):
            self._opm_with_keplerian(CenterName.CHARON, gm=None)

    def test_unknown_center_gm_provided_passes(self):
        opm = self._opm_with_keplerian(CenterName.CHARON, gm=102.3)
        assert opm.data.osculating_keplerian_elements.gm == 102.3


# ---------------------------------------------------------------------------
# Spec fixture round-trips (Annex G1-G5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"), _OPM_SPEC_FIXTURES, ids=[x[0] for x in _OPM_SPEC_FIXTURES]
)
def test_opm_spec_fixture_round_trip(name: str, fmt: str, tmp_path: Path) -> None:
    """Read spec fixture → write → semantic-diff → re-read. (CCSDS 502.0-B-3 Annex G)"""
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model_a = read(fixture, fmt=fmt, message_type="opm")
    out = tmp_path / name
    options = FIXTURE_WRITE_OPTIONS.get(name)
    write(model_a, out, options=options)
    assert_semantic_equal(fixture, out, fmt)
    model_b = read(out, fmt=fmt, message_type="opm")
    assert_models_equal(model_a, model_b)


# ---------------------------------------------------------------------------
# KVN round-trips (programmatic)
# ---------------------------------------------------------------------------


class TestOPMKVNRoundTrip:
    def test_state_vector_only(self, tmp_path: Path) -> None:
        """Minimal OPM: all header, metadata, state-vector fields survive KVN round-trip."""
        msg = make_opm()
        path = tmp_path / "test.opm"
        write(msg, path)
        back = read(path)
        assert_opm_equal(msg, back)

    def test_with_spacecraft_parameters(self, tmp_path: Path) -> None:
        msg = make_opm()
        opm = OPM(
            header=msg.header,
            metadata=msg.metadata,
            data=OPM.Data(
                state_vector=msg.data.state_vector,
                spacecraft_parameters=OPM.Data.SpacecraftParameters(
                    mass=3000.0,
                    solar_rad_area=18.77,
                    solar_rad_coeff=1.0,
                    drag_area=18.77,
                    drag_coeff=2.5,
                ),
            ),
        )
        path = tmp_path / "test.opm"
        write(opm, path)
        back = read(path)
        sp = back.data.spacecraft_parameters
        assert sp is not None
        assert sp.mass == pytest.approx(3000.0, rel=1e-9)
        assert sp.drag_coeff == pytest.approx(2.5, rel=1e-9)

    def test_with_keplerian_elements(self, tmp_path: Path) -> None:
        msg = make_opm()
        opm = OPM(
            header=msg.header,
            metadata=msg.metadata,
            data=OPM.Data(
                state_vector=msg.data.state_vector,
                osculating_keplerian_elements=OPM.Data.OsculatingKeplerianElements(
                    semi_major_axis=7000.0,
                    eccentricity=0.001,
                    inclination=51.6,
                    ra_of_asc_node=120.0,
                    arg_of_pericenter=30.0,
                    mean_anomaly=45.0,
                ),
            ),
        )
        path = tmp_path / "test.opm"
        write(opm, path)
        back = read(path)
        kep = back.data.osculating_keplerian_elements
        assert kep is not None
        assert kep.semi_major_axis == pytest.approx(7000.0, rel=1e-9)
        assert kep.mean_anomaly == pytest.approx(45.0, rel=1e-9)

    def test_with_maneuvers(self, tmp_path: Path) -> None:
        """Two maneuver blocks survive KVN round-trip in spec order (§3.2.4.8)."""
        msg = make_opm()
        opm = OPM(
            header=msg.header,
            metadata=msg.metadata,
            data=OPM.Data(
                state_vector=msg.data.state_vector,
                spacecraft_parameters=OPM.Data.SpacecraftParameters(mass=1000.0),
                maneuvers=[
                    OPM.Data.ManeuverParameters(
                        man_epoch_ignition="2020-001T01:00:00",
                        man_duration=0.0,
                        man_delta_mass=-1.0,
                        man_ref_frame=ManCovRefFrame.RTN,
                        man_dv_1=0.001,
                        man_dv_2=0.0,
                        man_dv_3=0.0,
                    ),
                    OPM.Data.ManeuverParameters(
                        man_epoch_ignition="2020-001T02:00:00",
                        man_duration=0.0,
                        man_delta_mass=-2.0,
                        man_ref_frame=ManCovRefFrame.TNW,
                        man_dv_1=0.002,
                        man_dv_2=0.001,
                        man_dv_3=0.0,
                    ),
                ],
            ),
        )
        path = tmp_path / "test.opm"
        write(opm, path)
        back = read(path)
        assert back.data.maneuvers is not None
        assert len(back.data.maneuvers) == 2
        assert back.data.maneuvers[0].man_dv_1 == pytest.approx(0.001, rel=1e-9)
        assert back.data.maneuvers[0].man_ref_frame == ManCovRefFrame.RTN
        assert back.data.maneuvers[1].man_dv_1 == pytest.approx(0.002, rel=1e-9)

    def test_with_covariance(self, tmp_path: Path) -> None:
        """All 21 covariance LTM elements survive KVN round-trip (§3.2.4.10)."""
        msg = make_opm()
        cov = OPM.Data.CovarianceMatrix(
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
        opm = OPM(
            header=msg.header,
            metadata=msg.metadata,
            data=OPM.Data(state_vector=msg.data.state_vector, covariance_matrix=cov),
        )
        path = tmp_path / "test.opm"
        write(opm, path)
        back = read(path)
        c = back.data.covariance_matrix
        assert c is not None
        assert c.cx_x == pytest.approx(3.33e-4, rel=1e-9)
        assert c.cz_dot_z_dot == pytest.approx(6.22e-10, rel=1e-9)

    def test_with_user_defined(self, tmp_path: Path) -> None:
        msg = make_opm()
        opm = OPM(
            header=msg.header,
            metadata=msg.metadata,
            data=OPM.Data(
                state_vector=msg.data.state_vector,
                user_defined=OPM.Data.UserDefinedParameters(
                    user_defined={"EARTH_MODEL": "WGS-84"}
                ),
            ),
        )
        path = tmp_path / "test.opm"
        write(opm, path)
        back = read(path)
        assert back.data.user_defined is not None
        assert back.data.user_defined.user_defined["EARTH_MODEL"] == "WGS-84"

    def test_idempotent(self, tmp_path: Path) -> None:
        """Write → read → write produces identical KVN output."""
        opm = make_opm()
        first = _OPM_WRITER.write_string(opm)
        second = _OPM_WRITER.write_string(_OPM_READER.read_string(first))
        assert first == second


# ---------------------------------------------------------------------------
# XML round-trips
# ---------------------------------------------------------------------------


class TestOPMXMLRoundTrip:
    def test_minimal(self, tmp_path: Path) -> None:
        msg = make_opm()
        path = tmp_path / "test.xml"
        write(msg, path, fmt="xml")
        back = read(path, fmt="xml", message_type="opm")
        assert_opm_equal(msg, back)

    def test_with_covariance(self, tmp_path: Path) -> None:
        msg = make_opm()
        cov = OPM.Data.CovarianceMatrix(
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
        opm = OPM(
            header=msg.header,
            metadata=msg.metadata,
            data=OPM.Data(state_vector=msg.data.state_vector, covariance_matrix=cov),
        )
        path = tmp_path / "test.xml"
        write(opm, path, fmt="xml")
        back = read(path, fmt="xml", message_type="opm")
        c = back.data.covariance_matrix
        assert c is not None
        assert c.cx_x == pytest.approx(3.33e-4, rel=1e-9)


# ---------------------------------------------------------------------------
# Builder API
# ---------------------------------------------------------------------------


class TestOPMBuilder:
    def test_build_minimal(self):
        opm = (
            OPM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )
            .state_vector(
                epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
            )
            .build()
        )
        assert opm.header.originator == "JAXA"
        assert opm.data.state_vector.x == 7000.0

    def test_build_with_spacecraft_and_maneuver(self):
        opm = (
            OPM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )
            .state_vector(
                epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
            )
            .spacecraft_parameters(mass=1200.0)
            .add_maneuver(
                man_epoch_ignition=EPOCH,
                man_duration=0.0,
                man_delta_mass=-1.0,
                man_ref_frame=ManCovRefFrame.RTN,
                man_dv_1=0.001,
                man_dv_2=0.0,
                man_dv_3=0.0,
            )
            .build()
        )
        assert opm.data.spacecraft_parameters.mass == 1200.0
        assert opm.data.maneuvers is not None
        assert len(opm.data.maneuvers) == 1

    def test_build_with_user_defined(self):
        opm = (
            OPM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )
            .state_vector(
                epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
            )
            .user_defined(EARTH_MODEL="WGS-84")
            .build()
        )
        assert opm.data.user_defined.user_defined["EARTH_MODEL"] == "WGS-84"

    def test_build_with_keplerian_elements(self):
        opm = (
            OPM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )
            .state_vector(
                epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
            )
            .keplerian_elements(
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                true_anomaly=0.0,
            )
            .build()
        )
        assert opm.data.osculating_keplerian_elements is not None
        assert opm.data.osculating_keplerian_elements.inclination == 51.6

    def test_build_with_covariance_matrix(self):
        opm = (
            OPM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )
            .state_vector(
                epoch=EPOCH, x=7000.0, y=0.0, z=0.0, x_dot=0.0, y_dot=7.5, z_dot=0.0
            )
            .covariance_matrix(
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
            .build()
        )
        assert opm.data.covariance_matrix is not None
        assert opm.data.covariance_matrix.cov_ref_frame == ManCovRefFrame.RTN

    def test_build_without_state_vector_raises(self):
        with pytest.raises(ValueError, match="state_vector"):
            OPM.builder().header(originator="JAXA", creation_date=CREATION_DATE).build()

    def test_builder_maneuver_valid_ref_frame_roundtrip(self):
        """Maneuver with RTN frame serializes and deserializes correctly."""
        opm = OPM(
            header=OPM.Header(
                ccsds_opm_vers="3.0", creation_date=CREATION_DATE, originator="JAXA"
            ),
            metadata=OPM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            ),
            data=OPM.Data(
                state_vector=OPM.Data.StateVector(
                    epoch=EPOCH,
                    x=7000.0,
                    y=0.0,
                    z=0.0,
                    x_dot=0.0,
                    y_dot=7.5,
                    z_dot=0.0,
                ),
                spacecraft_parameters=OPM.Data.SpacecraftParameters(mass=1000.0),
                maneuvers=[
                    OPM.Data.ManeuverParameters(
                        man_epoch_ignition="2020-001T01:00:00",
                        man_duration=0.0,
                        man_delta_mass=-1.0,
                        man_ref_frame=ManCovRefFrame.RTN,
                        man_dv_1=0.001,
                        man_dv_2=0.0,
                        man_dv_3=0.0,
                    )
                ],
            ),
        )
        serialized = _OPM_WRITER.write_string(opm)
        recovered = _OPM_READER.read_string(serialized)
        assert recovered.data.maneuvers is not None
        assert recovered.data.maneuvers[0].man_dv_1 == pytest.approx(0.001, rel=1e-9)
        assert recovered.data.maneuvers[0].man_ref_frame == ManCovRefFrame.RTN
