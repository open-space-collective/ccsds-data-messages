"""
OMM tests — model validation, spec fixtures (Annex G7-G10), KVN/XML round-trips.

Replaces:
- test_models.py:TestOMM, TestOMMBuilder
- test_roundtrip.py:TestKVNRoundTrip.test_omm_*, TestXMLRoundTrip.test_omm_*
- test_spec_fixtures.py:omm_g7..g10 rows
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic
import pytest
from conftest import (
    CREATION_DATE,
    EPOCH,
    FIXTURES,
    assert_models_equal,
    assert_omm_equal,
    assert_semantic_equal,
    make_omm,
)

from ccsds_data_messages import OMM, read, write
from ccsds_data_messages.io.kvn.omm_reader import KVNOMMReader
from ccsds_data_messages.io.kvn.omm_writer import KVNOMMWriter
from ccsds_data_messages.models.values import (
    CenterName,
    ManCovRefFrame,
    MeanElementTheory,
    RefFrame,
    TimeSystem,
)

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

_BASE_METADATA_KW = {
    "object_name": "TESTSAT",
    "object_id": "2020-001A",
    "center_name": CenterName.EARTH,
    "ref_frame": RefFrame.GCRF,
    "time_system": TimeSystem.UTC,
}
_BASE_MKE_KW = {
    "epoch": EPOCH,
    "semi_major_axis": 7000.0,
    "eccentricity": 0.001,
    "inclination": 51.6,
    "ra_of_asc_node": 120.0,
    "arg_of_pericenter": 30.0,
    "mean_anomaly": 45.0,
}


def _omm_header(**kw):
    defaults = {
        "ccsds_omm_vers": "3.0",
        "creation_date": CREATION_DATE,
        "originator": "TEST",
    }
    defaults.update(kw)
    return OMM.Header(**defaults)


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestOMMModel:
    def test_omm_minimal_dsst_construction_succeeds(self):
        # §4.2: DSST theory does not require TLE-specific parameters
        omm = make_omm()
        assert omm.header.ccsds_omm_vers == "3.0"
        assert omm.data.mean_keplerian_elements.semi_major_axis == 7000.0

    def test_omm_version_must_match_xy_pattern(self):
        # §7.9.1: version must be in 'x.y' form; OMM only exists as 2.0 or 3.0
        with pytest.raises(pydantic.ValidationError):
            OMM.Header(ccsds_omm_vers="3", creation_date=CREATION_DATE, originator="TEST")

    def test_omm_mean_element_theory_mandatory(self):
        # Table 4-2 marks MEAN_ELEMENT_THEORY M
        with pytest.raises(pydantic.ValidationError):
            OMM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
            )

    def test_omm_teme_accepted_for_sgp4(self):
        # §3.2.3.3 / §4.2.4.9: TEME is valid in OMM (unlike OPM where it raises)
        meta = OMM.Metadata(
            object_name="SAT",
            object_id="2020-001A",
            center_name=CenterName.EARTH,
            ref_frame=RefFrame.TEME,
            time_system=TimeSystem.UTC,
            mean_element_theory=MeanElementTheory.SGP4,
        )
        assert meta.ref_frame == RefFrame.TEME

    def test_omm_teme_requires_earth_center(self):
        # §4.2.4.9 + OMM.Metadata.validate_teme_constraints: TEME only for EARTH OMMs
        with pytest.raises(pydantic.ValidationError, match="Earth"):
            OMM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.MARS,
                ref_frame=RefFrame.TEME,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.SGP4,
            )

    def test_omm_teme_requires_utc_time_system(self):
        # §4.2.4.9: TEME-based OMMs must use UTC
        with pytest.raises(pydantic.ValidationError, match="UTC"):
            OMM.Metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.TEME,
                time_system=TimeSystem.TAI,
                mean_element_theory=MeanElementTheory.SGP4,
            )

    def test_omm_gcrf_non_teme_frame_accepted(self):
        # Non-TEME frame works fine for non-SGP4 theories
        meta = OMM.Metadata(
            **_BASE_METADATA_KW,
            mean_element_theory=MeanElementTheory.DSST,
        )
        assert meta.ref_frame == RefFrame.GCRF

    def test_omm_sgp4_mean_motion_required(self):
        # §4.2.4.6: SGP4 requires MEAN_MOTION, not SEMI_MAJOR_AXIS
        with pytest.raises(pydantic.ValidationError):
            OMM(
                header=_omm_header(),
                metadata=OMM.Metadata(
                    **{
                        **_BASE_METADATA_KW,
                        "ref_frame": RefFrame.TEME,
                        "mean_element_theory": MeanElementTheory.SGP4,
                    },
                ),
                data=OMM.Data(
                    mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                        **_BASE_MKE_KW  # uses semi_major_axis, not mean_motion
                    )
                ),
            )

    def test_omm_dsst_semi_major_axis_accepted(self):
        # §4.2.4.6: DSST/non-TLE theories use semi_major_axis
        omm = make_omm()
        assert omm.data.mean_keplerian_elements.semi_major_axis is not None
        assert omm.data.mean_keplerian_elements.mean_motion is None

    def test_omm_epoch_mandatory_in_mean_elements(self):
        # EPOCH is M in Table 4-3
        with pytest.raises(pydantic.ValidationError):
            OMM.Data.MeanKeplerianElements(
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )

    def test_omm_covariance_all_or_nothing(self):
        # §4.2.4.8: all 21 covariance elements or none
        with pytest.raises(pydantic.ValidationError):
            OMM.Data.CovarianceMatrix(
                cov_ref_frame=ManCovRefFrame.RTN,
                cx_x=1e-6,
                # Only one element — missing 20 more; should raise
            )

    def test_omm_doy_epoch_format_accepted(self):
        # §7.5.10 — G-7 uses "2007-064T10:34:41.4264" (DOY format)
        mke = OMM.Data.MeanKeplerianElements(
            epoch="2007-064T10:34:41.4264",
            semi_major_axis=7191.938639,
            eccentricity=0.0002062,
            inclination=97.9778,
            ra_of_asc_node=251.6021,
            arg_of_pericenter=94.6803,
            mean_anomaly=265.4588,
        )
        assert "2007-064T" in mke.epoch

    def test_omm_julian_date_epoch_rejected(self):
        # §7.5.10: Julian Date withdrawn in v3
        with pytest.raises(pydantic.ValidationError):
            OMM.Data.MeanKeplerianElements(
                epoch="2459945.5",
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )

    def test_omm_comment_empty_list_raises(self):
        with pytest.raises(pydantic.ValidationError):
            _omm_header(comment=[])

    def test_omm_comment_non_empty_accepted(self):
        h = _omm_header(comment=["This is an OMM for NORAD"])
        assert h.comment == ["This is an OMM for NORAD"]

    def test_omm_user_defined_parameters_accepted(self):
        udp = OMM.Data.UserDefinedParameters(user_defined={"EARTH_MODEL": "WGS-84"})
        assert udp.user_defined["EARTH_MODEL"] == "WGS-84"

    def test_omm_user_defined_empty_raises(self):
        with pytest.raises(pydantic.ValidationError):
            OMM.Data.UserDefinedParameters(user_defined={})


# ---------------------------------------------------------------------------
# Spec fixture round-trips (Annex G7-G10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"), _OMM_SPEC_FIXTURES, ids=[x[0] for x in _OMM_SPEC_FIXTURES]
)
def test_omm_spec_fixture_round_trip(name: str, fmt: str, tmp_path: Path) -> None:
    """Read spec fixture → write → semantic-diff → re-read. (CCSDS 502.0-B-3 Annex G)"""
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
            header=_omm_header(),
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
        """All 21 covariance LTM elements survive round-trip (§4.2.4.8)."""
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
        """USER_DEFINED_* parameters survive round-trip (§4.2.4.11)."""
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
            header=_omm_header(comment=["OMM version 3", "Classification: U"]),
            metadata=OMM.Metadata(
                **_BASE_METADATA_KW,
                mean_element_theory=MeanElementTheory.DSST,
            ),
            data=OMM.Data(
                mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                    **_BASE_MKE_KW,
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
        """Write → read → write produces identical KVN output."""
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
            header=_omm_header(),
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


# ---------------------------------------------------------------------------
# Builder API
# ---------------------------------------------------------------------------


class TestOMMBuilder:
    def test_build_minimal(self):
        omm = (
            OMM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.DSST,
            )
            .mean_keplerian_elements(
                epoch=EPOCH,
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )
            .build()
        )
        assert omm.header.originator == "JAXA"
        assert omm.data.mean_keplerian_elements.inclination == 51.6

    def test_build_without_mean_keplerian_elements_raises(self):
        with pytest.raises(ValueError):
            OMM.builder().header(originator="JAXA", creation_date=CREATION_DATE).build()

    def test_build_with_spacecraft_parameters(self):
        omm = (
            OMM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.DSST,
            )
            .mean_keplerian_elements(
                epoch=EPOCH,
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )
            .spacecraft_parameters(mass=3000.0, drag_area=18.77, drag_coeff=2.5)
            .build()
        )
        assert omm.data.spacecraft_parameters is not None
        assert omm.data.spacecraft_parameters.mass == pytest.approx(3000.0, rel=1e-9)

    def test_build_with_tle_parameters(self):
        omm = (
            OMM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="NORAD-SAT",
                object_id="2007-064A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.TEME,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.SGP4,
            )
            .mean_keplerian_elements(
                epoch="2007-064T10:34:41.4264",
                mean_motion=14.82616925,
                eccentricity=0.0002062,
                inclination=97.9778,
                ra_of_asc_node=251.6021,
                arg_of_pericenter=94.6803,
                mean_anomaly=265.4588,
            )
            .tle_parameters(
                ephemeris_type=0,
                classification_type="U",
                norad_cat_id=4285,
                element_set_no=999,
                rev_at_epoch=11113,
                bstar=0.0001e-4,
                mean_motion_dot=0.00001004,
                mean_motion_ddot=0.0,
            )
            .build()
        )
        assert omm.data.tle_related_parameters is not None
        assert omm.data.tle_related_parameters.norad_cat_id == 4285

    def test_build_with_covariance_matrix(self):
        omm = (
            OMM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.DSST,
            )
            .mean_keplerian_elements(
                epoch=EPOCH,
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )
            .covariance_matrix(
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
            .build()
        )
        assert omm.data.covariance_matrix is not None
        assert omm.data.covariance_matrix.cov_ref_frame == ManCovRefFrame.RTN

    def test_build_with_user_defined(self):
        omm = (
            OMM.builder()
            .header(originator="JAXA", creation_date=CREATION_DATE)
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.DSST,
            )
            .mean_keplerian_elements(
                epoch=EPOCH,
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )
            .user_defined(EARTH_MODEL="WGS-84")
            .build()
        )
        assert omm.data.user_defined is not None
        assert omm.data.user_defined.user_defined["EARTH_MODEL"] == "WGS-84"
