"""
OMM-to-TLE conversion tests.

Modules under test:
    src/ccsds_data_messages/models/conversions.py (omm_to_tle)
    src/ccsds_data_messages/models/_tle_codec.py (encoders)
    src/ccsds_data_messages/models/tle.py (TLE value object)

The two golden cases assert byte-for-byte equality against real element sets
published by CelesTrak (https://celestrak.org), the canonical interoperability
reference for the OMM/TLE representations.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OMM
from ccsds_data_messages import TLE
from ccsds_data_messages import MessageFormat
from ccsds_data_messages import MessageType
from ccsds_data_messages import omm_to_tle
from ccsds_data_messages import read_omm
from ccsds_data_messages import read_string
from ccsds_data_messages.models._tle_codec import _alpha5
from ccsds_data_messages.models._tle_codec import _assumed_decimal_exp
from ccsds_data_messages.models._tle_codec import _checksum
from ccsds_data_messages.models._tle_codec import _intl_designator
from ccsds_data_messages.models._tle_codec import _signed_decimal_fraction
from ccsds_data_messages.models.values import CenterName
from ccsds_data_messages.models.values import MeanElementTheory
from ccsds_data_messages.models.values import RefFrame
from ccsds_data_messages.models.values import TimeSystem

# (case_id, norad_cat_id, expected 5-char field). Letters skip I and O.
_ALPHA5_CASES = [
    ("plain-small", 925, "00925"),
    ("plain-max", 99_999, "99999"),
    ("letter-min", 100_000, "A0000"),
    ("letter-mid", 148_493, "E8493"),
    ("letter-max", 339_999, "Z9999"),
]

# (case_id, value, expected 10-char ".NNNNNNNN" field).
_SIGNED_FRACTION_CASES = [
    ("positive", 0.00005896, " .00005896"),
    ("negative", -5.65e-7, "-.00000056"),
    ("zero", 0.0, " .00000000"),
]

# (case_id, value, expected 8-char decimal-point-assumed exponential field).
_ASSUMED_EXP_CASES = [
    ("zero", 0.0, " 00000+0"),
    ("bstar", 0.11479289e-3, " 11479-3"),
    ("negative", -1.1606e-4, "-11606-3"),
    ("exact-power", 1e-4, " 10000-3"),
]

# (case_id, object_id, expected 8-char international-designator field).
_INTL_DESIGNATOR_CASES = [
    ("iss", "1998-067A", "98067A  "),
    ("goes9", "1995-025A", "95025A  "),
    ("unknown", "UNKNOWN", "        "),
]


def _sgp4_omm(
    *,
    metadata: dict[str, Any] | None = None,
    mean_keplerian_elements: dict[str, Any] | None = None,
    tle_parameters: dict[str, Any] | None = None,
) -> OMM:
    """Build a valid SGP4 (TEME) OMM, with optional per-block overrides."""
    meta = {
        "object_name": "TESTSAT",
        "object_id": "2020-001A",
        "center_name": CenterName.EARTH,
        "ref_frame": RefFrame.TEME,
        "time_system": TimeSystem.UTC,
        "mean_element_theory": MeanElementTheory.SGP4,
    }
    mke = {
        "epoch": "2020-001T00:00:00.000",
        "mean_motion": 15.5,
        "eccentricity": 0.0012,
        "inclination": 51.6,
        "ra_of_asc_node": 120.0,
        "arg_of_pericenter": 30.0,
        "mean_anomaly": 45.0,
    }
    tle = {"norad_cat_id": 25544, "bstar": 1e-4}
    meta.update(metadata or {})
    mke.update(mean_keplerian_elements or {})
    tle.update(tle_parameters or {})
    return (
        OMM.builder()
        .header(originator="TEST", creation_date="2020-001T00:00:00")
        .metadata(**meta)
        .mean_keplerian_elements(**mke)
        .tle_parameters(**tle)
        .build()
    )


class TestGoldenCases:
    def test_iss_matches_celestrak(self):
        """
        CelesTrak OMM -> TLE reproduces CelesTrak's published TLE byte-for-byte.

        Both fixtures are verbatim CelesTrak payloads for ISS (25544):
        gp.php?CATNR=25544&FORMAT=KVN and &FORMAT=TLE. CelesTrak leaves the
        CCSDS-mandatory CREATION_DATE and ORIGINATOR blank, which the strict reader
        rejects, so the test fills them; neither field affects the generated TLE.
        """
        raw = (FIXTURES / "omm_celestrak_iss_25544.kvn").read_text()
        patched_lines = []
        for line in raw.splitlines():
            if line.startswith("CREATION_DATE"):
                patched_lines.append("CREATION_DATE  = 2026-202T04:27:10")
            elif line.startswith("ORIGINATOR"):
                patched_lines.append("ORIGINATOR     = CELESTRAK")
            else:
                patched_lines.append(line)

        omm = read_string("\n".join(patched_lines), MessageFormat.KVN, MessageType.OMM)
        tle = omm_to_tle(omm)

        expected = (FIXTURES / "tle_celestrak_iss_25544.txt").read_text().splitlines()
        assert tle.name == expected[0]
        assert tle.line1 == expected[1]
        assert tle.line2 == expected[2]

    def test_goes9_spec_fixture(self):
        """The CCSDS Annex G G-7 OMM fixture converts to a valid 69-char TLE."""
        tle = omm_to_tle(read_omm(FIXTURES / "omm_g7.kvn"))
        assert tle.name == "GOES 9"
        assert tle.line1 == (
            "1 23581U 95025A   20064.44075725 -.00000113  00000+0  10000-3 0  9254"
        )
        assert tle.line2 == (
            "2 23581   3.0539  81.7939 0005013 249.2363 150.1602  1.00273272 43169"
        )


class TestTleStructure:
    def test_both_lines_are_69_chars(self):
        tle = omm_to_tle(_sgp4_omm())
        assert len(tle.line1) == 69
        assert len(tle.line2) == 69

    def test_checksums_are_valid(self):
        tle = omm_to_tle(_sgp4_omm())
        for line in (tle.line1, tle.line2):
            assert int(line[68]) == _checksum(line[:68])

    def test_str_is_two_line(self):
        tle = omm_to_tle(_sgp4_omm())
        assert str(tle) == f"{tle.line1}\n{tle.line2}"

    def test_three_line_prepends_title(self):
        tle = omm_to_tle(_sgp4_omm(metadata={"object_name": "TESTSAT"}))
        assert tle.three_line() == f"TESTSAT\n{tle.line1}\n{tle.line2}"


class TestAlpha5:
    @pytest.mark.parametrize(
        ("case_id", "norad_cat_id", "expected"),
        _ALPHA5_CASES,
        ids=[c[0] for c in _ALPHA5_CASES],
    )
    def test_alpha5(self, case_id: str, norad_cat_id: int, expected: str):
        assert _alpha5(norad_cat_id) == expected

    def test_conversion_uses_alpha5_on_both_lines(self):
        tle = omm_to_tle(_sgp4_omm(tle_parameters={"norad_cat_id": 123456}))
        assert tle.line1[2:7] == "C3456"
        assert tle.line2[2:7] == "C3456"

    def test_overflow_raises(self):
        with pytest.raises(ValueError, match="Alpha-5"):
            omm_to_tle(_sgp4_omm(tle_parameters={"norad_cat_id": 340000}))

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            _alpha5(-1)


class TestEncoding:
    @pytest.mark.parametrize(
        ("case_id", "value", "expected"),
        _SIGNED_FRACTION_CASES,
        ids=[c[0] for c in _SIGNED_FRACTION_CASES],
    )
    def test_signed_decimal_fraction(self, case_id: str, value: float, expected: str):
        assert _signed_decimal_fraction(value) == expected

    def test_signed_decimal_fraction_out_of_range_raises(self):
        with pytest.raises(ValueError, match="TLE field"):
            _signed_decimal_fraction(1.5)

    @pytest.mark.parametrize(
        ("case_id", "value", "expected"),
        _ASSUMED_EXP_CASES,
        ids=[c[0] for c in _ASSUMED_EXP_CASES],
    )
    def test_assumed_decimal_exp(self, case_id: str, value: float, expected: str):
        assert _assumed_decimal_exp(value) == expected

    def test_assumed_decimal_exp_exponent_overflow_raises(self):
        # An exponent needing two digits does not fit the single-digit TLE field.
        with pytest.raises(ValueError, match="exponent"):
            _assumed_decimal_exp(1e-11)

    @pytest.mark.parametrize(
        ("case_id", "object_id", "expected"),
        _INTL_DESIGNATOR_CASES,
        ids=[c[0] for c in _INTL_DESIGNATOR_CASES],
    )
    def test_intl_designator(self, case_id: str, object_id: str, expected: str):
        assert _intl_designator(object_id) == expected

    def test_checksum_counts_minus_as_one(self):
        # Two digits (1 + 2) plus one minus sign = 4.
        assert _checksum("12-") == 4


class TestGuards:
    def test_incompatible_theory_raises(self):
        # DSST uses semi-major axis and no TLE block; reject before field access.
        omm = (
            OMM.builder()
            .header(originator="TEST", creation_date="2020-001T00:00:00")
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                mean_element_theory=MeanElementTheory.DSST,
            )
            .mean_keplerian_elements(
                epoch="2020-001T00:00:00.000",
                semi_major_axis=7000.0,
                eccentricity=0.001,
                inclination=51.6,
                ra_of_asc_node=0.0,
                arg_of_pericenter=0.0,
                mean_anomaly=0.0,
            )
            .build()
        )
        with pytest.raises(ValueError, match="cannot be represented"):
            omm_to_tle(omm)

    def _non_teme_omm(self, *, with_mean_motion: bool, with_tle_block: bool) -> OMM:
        # A non-SGP/SGP4 theory in a non-TEME frame, so the OMM validates without a
        # TLE block; used to exercise the converter's own preconditions.
        builder = (
            OMM.builder()
            .header(originator="TEST", creation_date="2020-001T00:00:00")
            .metadata(
                object_name="SAT",
                object_id="2020-001A",
                center_name=CenterName.EARTH,
                ref_frame=RefFrame.GCRF,
                time_system=TimeSystem.UTC,
                mean_element_theory="CUSTOM",
            )
        )
        mke = {
            "epoch": "2020-001T00:00:00.000",
            "eccentricity": 0.001,
            "inclination": 51.6,
            "ra_of_asc_node": 0.0,
            "arg_of_pericenter": 0.0,
            "mean_anomaly": 0.0,
        }
        mke["mean_motion" if with_mean_motion else "semi_major_axis"] = (
            15.5 if with_mean_motion else 7000.0
        )
        builder = builder.mean_keplerian_elements(**mke)
        if with_tle_block:
            builder = builder.tle_parameters(norad_cat_id=25544)
        return builder.build()

    def test_missing_mean_motion_raises(self):
        omm = self._non_teme_omm(with_mean_motion=False, with_tle_block=False)
        with pytest.raises(ValueError, match="MEAN_MOTION"):
            omm_to_tle(omm)

    def test_missing_tle_block_raises(self):
        omm = self._non_teme_omm(with_mean_motion=True, with_tle_block=False)
        with pytest.raises(ValueError, match="NORAD_CAT_ID"):
            omm_to_tle(omm)

    def test_bterm_raises(self):
        # An SGP4-XP-style OMM carries BTERM, which a classic TLE has no field for.
        # Built as SGP (TEME is only valid for SGP/SGP4) with a stray BTERM so the
        # OMM validates and the converter's BTERM guard is what rejects it.
        omm = _sgp4_omm(
            metadata={"mean_element_theory": MeanElementTheory.SGP},
            tle_parameters={
                "bstar": None,
                "bterm": 0.01,
                "mean_motion_dot": 1e-6,
                "mean_motion_ddot": 0.0,
            },
        )
        with pytest.raises(ValueError, match="cannot be represented"):
            omm_to_tle(omm)


class TestTleModel:
    def test_rejects_wrong_length(self):
        with pytest.raises(ValueError, match="69 characters"):
            TLE(name="SAT", line1="1 short", line2="2 " + "0" * 67)

    def test_rejects_wrong_leading_digit(self):
        with pytest.raises(ValueError, match="must begin with"):
            TLE(name="SAT", line1="9" + "0" * 68, line2="2" + "0" * 68)

    def test_is_frozen(self):
        tle = omm_to_tle(_sgp4_omm())
        with pytest.raises(ValueError):
            tle.name = "OTHER"  # type: ignore[misc]
