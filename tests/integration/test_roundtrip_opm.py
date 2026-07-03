"""
OPM serialization round-trip tests (KVN + XML, spec Annex G1-G5).

Module under test: src/ccsds_data_messages/io/kvn/opm_*.py, io/xml/opm_*.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import CREATION_DATE
from conftest import EPOCH
from conftest import FIXTURE_WRITE_OPTIONS
from conftest import FIXTURES
from conftest import assert_models_equal
from conftest import assert_opm_equal
from conftest import assert_semantic_equal
from conftest import make_opm

from ccsds_data_messages import OPM
from ccsds_data_messages import read
from ccsds_data_messages import write
from ccsds_data_messages.io.kvn.opm_reader import KVNOPMReader
from ccsds_data_messages.io.kvn.opm_writer import KVNOPMWriter
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import ManCovRefFrame
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

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
# Spec fixture round-trips (Annex G1-G5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"), _OPM_SPEC_FIXTURES, ids=[x[0] for x in _OPM_SPEC_FIXTURES]
)
def test_opm_spec_fixture_round_trip(name: str, fmt: str, tmp_path: Path) -> None:
    """Read a spec fixture, write it, semantic-diff, then re-read. (CCSDS 502.0-B-3 Annex G)"""
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
        """Two maneuver blocks survive KVN round-trip in spec order (section 3.2.4.8)."""
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
        """All 21 covariance LTM elements survive KVN round-trip (section 3.2.4.10)."""
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
        """Write, read, then write again produces identical KVN output."""
        opm = make_opm()
        first = _OPM_WRITER.write_string(opm)
        second = _OPM_WRITER.write_string(_OPM_READER.read_string(first))
        assert first == second

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
