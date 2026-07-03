"""
OMM serialization round-trip tests (KVN + XML).

Covers spec-fixture round-trips (Annex G7-G10) and programmatic
KVN/XML read/write round-trips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import FIXTURES
from conftest import OMM_BASE_METADATA_KW
from conftest import OMM_BASE_MKE_KW
from conftest import assert_models_equal
from conftest import assert_omm_equal
from conftest import assert_semantic_equal
from conftest import make_omm
from conftest import make_omm_header

from ccsds_data_messages import OMM
from ccsds_data_messages import read
from ccsds_data_messages import write
from ccsds_data_messages.io.kvn.omm_reader import KVNOMMReader
from ccsds_data_messages.io.kvn.omm_writer import KVNOMMWriter
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import ManCovRefFrame
from ccsds_data_messages.models.values import MeanElementTheory
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

if TYPE_CHECKING:
    from pathlib import Path

_OMM_READER = KVNOMMReader()
_OMM_WRITER = KVNOMMWriter()

_OMM_SPEC_FIXTURES = [
    ("omm_g7.kvn", "kvn"),
    ("omm_g8_covariance.kvn", "kvn"),
    ("omm_g9_units.kvn", "kvn"),
    ("omm_g10.xml", "xml"),
]

# ---------------------------------------------------------------------------
# Spec fixture round-trips (Annex G7-G10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"), _OMM_SPEC_FIXTURES, ids=[x[0] for x in _OMM_SPEC_FIXTURES]
)
def test_omm_spec_fixture_round_trip(name: str, fmt: str, tmp_path: Path) -> None:
    """Read a spec fixture, write it, semantic-diff, then re-read. (CCSDS 502.0-B-3 Annex G)"""
    fixture = FIXTURES / name
    assert fixture.exists(), f"Fixture not found: {fixture}"
    model_a = read(fixture, fmt=fmt, message_type="omm")
    out = tmp_path / name
    write(model_a, out)
    assert_semantic_equal(fixture, out, fmt)
    model_b = read(out, fmt=fmt, message_type="omm")
    assert_models_equal(model_a, model_b)


# ---------------------------------------------------------------------------
# KVN round-trips (programmatic)
# ---------------------------------------------------------------------------


class TestOMMKVNRoundTrip:
    def test_dsst_semi_major_axis(self, tmp_path: Path) -> None:
        """DSST OMM (semi_major_axis, no mean_motion) round-trips correctly."""
        msg = make_omm()
        path = tmp_path / "test.omm"
        write(msg, path)
        back = read(path, message_type="omm")
        assert_omm_equal(msg, back)

    def test_sgp4_mean_motion(self, tmp_path: Path) -> None:
        """SGP4 OMM (mean_motion, TEME, BSTAR) round-trips correctly."""
        omm = OMM(
            header=make_omm_header(),
            metadata=OMM.Metadata(
                object_name="NORAD-SAT",
                object_id="2007-064A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.TEME,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.SGP4,
            ),
            data=OMM.Data(
                mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                    epoch="2007-064T10:34:41.4264",
                    mean_motion=14.82616925,
                    eccentricity=0.0002062,
                    inclination=97.9778,
                    ra_of_asc_node=251.6021,
                    arg_of_pericenter=94.6803,
                    mean_anomaly=265.4588,
                ),
                tle_related_parameters=OMM.Data.TLERelatedParameters(
                    ephemeris_type=0,
                    classification_type="U",
                    norad_cat_id=4285,
                    element_set_no=999,
                    rev_at_epoch=11113,
                    bstar=0.0001e-4,
                    mean_motion_dot=0.00001004,
                    mean_motion_ddot=0.0,
                ),
            ),
        )
        path = tmp_path / "test.omm"
        write(omm, path)
        back = read(path, message_type="omm")
        assert back.metadata.ref_frame == RefFrame.TEME
        assert back.data.mean_keplerian_elements.mean_motion == pytest.approx(
            14.82616925, rel=1e-9
        )
        tle = back.data.tle_related_parameters
        assert tle is not None
        assert tle.norad_cat_id == 4285

    def test_with_spacecraft_parameters(self, tmp_path: Path) -> None:
        """Mass, drag area, solar radiation coefficient survive round-trip."""
        msg = make_omm()
        omm = OMM(
            header=msg.header,
            metadata=msg.metadata,
            data=OMM.Data(
                mean_keplerian_elements=msg.data.mean_keplerian_elements,
                spacecraft_parameters=OMM.Data.SpacecraftParameters(
                    mass=3000.0,
                    drag_area=18.77,
                    drag_coeff=2.5,
                ),
            ),
        )
        path = tmp_path / "test.omm"
        write(omm, path)
        back = read(path, message_type="omm")
        sp = back.data.spacecraft_parameters
        assert sp is not None
        assert sp.mass == pytest.approx(3000.0, rel=1e-9)
        assert sp.drag_coeff == pytest.approx(2.5, rel=1e-9)

    def test_with_covariance(self, tmp_path: Path) -> None:
        """All 21 covariance LTM elements survive round-trip (section 4.2.4.8)."""
        msg = make_omm()
        cov = OMM.Data.CovarianceMatrix(
            cov_ref_frame=ManCovRefFrame.RTN,
            cx_x=3.331349476038534e-4,
            cy_x=4.618927349220216e-4,
            cy_y=6.782421679971363e-4,
            cz_x=-3.070007847730449e-4,
            cz_y=-4.221234189514228e-4,
            cz_z=3.231931992380369e-4,
            cx_dot_x=-3.349365033922630e-7,
            cx_dot_y=-4.686084221046758e-7,
            cx_dot_z=2.484949578400095e-7,
            cx_dot_x_dot=4.29030763e-10,
            cy_dot_x=-2.214164846604875e-7,
            cy_dot_y=-2.864186892102733e-7,
            cy_dot_z=1.798098699846038e-7,
            cy_dot_x_dot=2.608899201686016e-10,
            cy_dot_y_dot=1.767514756338532e-10,
            cz_dot_x=-3.041089940006847e-7,
            cz_dot_y=-4.989496988610662e-7,
            cz_dot_z=3.540310854290761e-7,
            cz_dot_x_dot=1.86030895e-10,
            cz_dot_y_dot=1.00422633e-10,
            cz_dot_z_dot=6.22186959e-10,
        )
        omm = OMM(
            header=msg.header,
            metadata=msg.metadata,
            data=OMM.Data(
                mean_keplerian_elements=msg.data.mean_keplerian_elements,
                covariance_matrix=cov,
            ),
        )
        path = tmp_path / "test.omm"
        write(omm, path)
        back = read(path, message_type="omm")
        c = back.data.covariance_matrix
        assert c is not None
        assert c.cx_x == pytest.approx(3.331349476038534e-4, rel=1e-9)
        assert c.cz_dot_z_dot == pytest.approx(6.22186959e-10, rel=1e-9)

    def test_with_user_defined(self, tmp_path: Path) -> None:
        """USER_DEFINED_* parameters survive round-trip (section 4.2.4.11)."""
        msg = make_omm()
        omm = OMM(
            header=msg.header,
            metadata=msg.metadata,
            data=OMM.Data(
                mean_keplerian_elements=msg.data.mean_keplerian_elements,
                user_defined=OMM.Data.UserDefinedParameters(
                    user_defined={"EARTH_MODEL": "EGM96"}
                ),
            ),
        )
        path = tmp_path / "test.omm"
        write(omm, path)
        back = read(path, message_type="omm")
        assert back.data.user_defined.user_defined["EARTH_MODEL"] == "EGM96"

    def test_comments_preserved(self, tmp_path: Path) -> None:
        """Header and mean_keplerian_elements comments survive round-trip."""
        omm = OMM(
            header=make_omm_header(comment=["OMM version 3", "Classification: U"]),
            metadata=OMM.Metadata(
                **OMM_BASE_METADATA_KW,
                mean_element_theory=MeanElementTheory.DSST,
            ),
            data=OMM.Data(
                mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                    **OMM_BASE_MKE_KW,
                    comment=["Elements derived by TDRSS"],
                ),
            ),
        )
        path = tmp_path / "test.omm"
        write(omm, path)
        back = read(path, message_type="omm")
        assert back.header.comment == ["OMM version 3", "Classification: U"]
        assert back.data.mean_keplerian_elements.comment == ["Elements derived by TDRSS"]

    def test_idempotent(self, tmp_path: Path) -> None:
        """Write, read, then write again produces identical KVN output."""
        omm = make_omm()
        first = _OMM_WRITER.write_string(omm)
        second = _OMM_WRITER.write_string(_OMM_READER.read_string(first))
        assert first == second


# ---------------------------------------------------------------------------
# XML round-trips
# ---------------------------------------------------------------------------


class TestOMMXMLRoundTrip:
    def test_minimal_dsst(self, tmp_path: Path) -> None:
        msg = make_omm()
        path = tmp_path / "test.xml"
        write(msg, path, fmt="xml")
        back = read(path, fmt="xml", message_type="omm")
        assert_omm_equal(msg, back)

    def test_sgp4_with_tle_parameters(self, tmp_path: Path) -> None:
        """SGP4 OMM in XML round-trips; all TLE fields present."""
        omm = OMM(
            header=make_omm_header(),
            metadata=OMM.Metadata(
                object_name="NORAD-SAT",
                object_id="2007-064A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.TEME,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.SGP4,
            ),
            data=OMM.Data(
                mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                    epoch="2007-064T10:34:41.4264",
                    mean_motion=14.82616925,
                    eccentricity=0.0002062,
                    inclination=97.9778,
                    ra_of_asc_node=251.6021,
                    arg_of_pericenter=94.6803,
                    mean_anomaly=265.4588,
                ),
                tle_related_parameters=OMM.Data.TLERelatedParameters(
                    ephemeris_type=0,
                    classification_type="U",
                    norad_cat_id=4285,
                    element_set_no=999,
                    rev_at_epoch=11113,
                    bstar=0.0001e-4,
                    mean_motion_dot=0.00001004,
                    mean_motion_ddot=0.0,
                ),
            ),
        )
        path = tmp_path / "test.xml"
        write(omm, path, fmt="xml")
        back = read(path, fmt="xml", message_type="omm")
        assert back.metadata.ref_frame == RefFrame.TEME
        assert back.data.tle_related_parameters.norad_cat_id == 4285

    def test_with_covariance(self, tmp_path: Path) -> None:
        """21 covariance elements survive XML round-trip."""
        msg = make_omm()
        cov = OMM.Data.CovarianceMatrix(
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
        omm = OMM(
            header=msg.header,
            metadata=msg.metadata,
            data=OMM.Data(
                mean_keplerian_elements=msg.data.mean_keplerian_elements,
                covariance_matrix=cov,
            ),
        )
        path = tmp_path / "test.xml"
        write(omm, path, fmt="xml")
        back = read(path, fmt="xml", message_type="omm")
        c = back.data.covariance_matrix
        assert c is not None
        assert c.cx_x == pytest.approx(3.33e-4, rel=1e-9)
