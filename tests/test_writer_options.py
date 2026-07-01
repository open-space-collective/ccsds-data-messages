"""
WriterOptions behavior tests.

Covers align_keywords, float_formats, include_units, align_data_columns,
suppress_defaults. Module under test: src/ccsds_data_messages/io/options.py
"""

from __future__ import annotations

import re

import pytest
from conftest import CREATION_DATE, EPOCH, FIXTURES, make_oem, make_opm

from ccsds_data_messages import OCM, OMM, read
from ccsds_data_messages.io.kvn.ocm_writer import KVNOCMWriter
from ccsds_data_messages.io.kvn.oem_writer import KVNOEMWriter
from ccsds_data_messages.io.kvn.omm_writer import KVNOMMWriter
from ccsds_data_messages.io.kvn.opm_writer import KVNOPMWriter
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models.values import (
    CenterName,
    MeanElementTheory,
    RefFrame,
    TimeSystem,
)

_OPM_WRITER = KVNOPMWriter()
_OEM_WRITER = KVNOEMWriter()
_OMM_WRITER = KVNOMMWriter()


class TestAlignKeywords:
    def test_align_keywords_true_pads_within_each_block(self):
        """With align_keywords=True, keywords within each block are padded to equal width."""
        opm = make_opm()
        opts = WriterOptions(align_keywords=True)
        output = _OPM_WRITER.write_string(opm, options=opts)
        # Within the state-vector block (EPOCH, X, Y, Z, X_DOT, Y_DOT, Z_DOT),
        # shorter keywords should be right-padded with spaces before '='
        lines = output.splitlines()
        sv_lines = [
            line
            for line in lines
            if line.strip().startswith(("X ", "Y ", "Z ", "X_DOT", "Y_DOT", "Z_DOT"))
        ]
        eq_positions = [line.index("=") for line in sv_lines if "=" in line]
        assert len(set(eq_positions)) == 1, (
            f"State-vector keywords should align within block; positions: {eq_positions}"
        )

    def test_align_keywords_false_produces_compact_output(self):
        """With align_keywords=False, differently-sized keywords are NOT padded to align."""
        opm = make_opm()
        opts = WriterOptions(align_keywords=False)
        output = _OPM_WRITER.write_string(opm, options=opts)
        # Same state-vector block as the align=True case above: without padding,
        # "X"/"Y"/"Z" (1 char) and "X_DOT"/"Y_DOT"/"Z_DOT" (5 chars) put '=' at
        # different columns instead of a shared aligned column.
        sv_lines = [
            line
            for line in output.splitlines()
            if line.strip().startswith(("X ", "Y ", "Z ", "X_DOT", "Y_DOT", "Z_DOT"))
        ]
        eq_positions = [line.index("=") for line in sv_lines if "=" in line]
        assert len(set(eq_positions)) > 1, (
            f"Without alignment, '=' positions should differ; positions: {eq_positions}"
        )


class TestFloatFormats:
    def test_float_formats_override_applies_to_specified_keyword(self):
        """WriterOptions(float_formats={'X': '.15g'}) → X line uses 15 sig figs."""
        opm = make_opm(state_vector={"x": 7000.123456789012345})
        opts = WriterOptions(float_formats={"X": ".15g"})
        output = _OPM_WRITER.write_string(opm, options=opts)
        # The X line must contain a string with many significant digits
        x_lines = [line for line in output.splitlines() if line.strip().startswith("X ")]
        assert x_lines, "No 'X = ...' line found in output"
        x_line = x_lines[0]
        value_str = x_line.split("=")[1].strip().split()[0]
        # Must have more digits than the default 6-significant-digit representation
        assert len(value_str.replace(".", "").replace("-", "").lstrip("0")) > 6

    def test_float_formats_unspecified_keyword_uses_default(self):
        """Keywords not in float_formats use the model's default format_spec."""
        opm = make_opm()
        opts = WriterOptions(float_formats={"X": ".15g"})
        output = _OPM_WRITER.write_string(opm, options=opts)
        # Y line should still exist; the value should be a valid float string
        y_lines = [line for line in output.splitlines() if line.strip().startswith("Y ")]
        assert y_lines, "No 'Y = ...' line found in output"

    def test_float_formats_empty_uses_defaults(self):
        """Empty float_formats dict uses default formatting for all fields."""
        opm = make_opm()
        opts = WriterOptions(float_formats={})
        output_default = _OPM_WRITER.write_string(opm)
        output_explicit = _OPM_WRITER.write_string(opm, options=opts)
        assert output_default == output_explicit


def _data_line_column_ends(output: str) -> list[tuple[int, ...]]:
    """Per-line end offsets of each whitespace-delimited field, for column-position checks."""
    data_lines = [
        line
        for line in output.splitlines()
        if line.strip() and line.strip()[0].isdigit() and "T" in line.split()[0]
    ]
    return [tuple(m.end() for m in re.finditer(r"\S+", line)) for line in data_lines]


class TestAlignDataColumns:
    def test_align_data_columns_true_produces_right_justified_columns(self):
        """With align_data_columns=True, each column ends at the same offset in every row."""
        # y ranges 0/200/400/600/800 (1 vs 3 integer digits) across rows, so this
        # would fail without real right-justification forcing a shared column width.
        oem = make_oem(n_lines=5)
        opts = WriterOptions(align_data_columns=True)
        output = _OEM_WRITER.write_string(oem, options=opts)
        column_ends = _data_line_column_ends(output)
        assert len(column_ends) == 5
        assert len({len(row) for row in column_ends}) == 1, (
            "All rows should have 7 fields"
        )
        assert len(set(column_ends)) == 1, (
            f"Aligned columns should end at the same offset in every row: {column_ends}"
        )

    def test_align_data_columns_false_produces_unaligned_columns(self):
        """With align_data_columns=False, natural formatting leaves column offsets differing."""
        oem = make_oem(n_lines=5)
        opts = WriterOptions(align_data_columns=False)
        output = _OEM_WRITER.write_string(oem, options=opts)
        column_ends = _data_line_column_ends(output)
        assert len(column_ends) == 5
        assert len(set(column_ends)) > 1, (
            f"Unaligned columns should not all end at the same offsets: {column_ends}"
        )


def _make_sgp4_omm(*, ephemeris_type: int | None) -> OMM:
    """SGP4 OMM whose TLE-related EPHEMERIS_TYPE matches its FieldMetadata(spec_default=0)."""
    return OMM(
        header=OMM.Header(
            ccsds_omm_vers="3.0", originator="TEST", creation_date=CREATION_DATE
        ),
        metadata=OMM.Metadata(
            object_name="TESTSAT",
            object_id="2020-001A",
            center_name=CenterName.EARTH,
            ref_frame=RefFrame.TEME,
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
                mean_motion=15.2,
            ),
            tle_related_parameters=OMM.Data.TLERelatedParameters(
                ephemeris_type=ephemeris_type,
                norad_cat_id=25544,
                bstar=2.8098e-5,
                mean_motion_dot=6.969196e-13,
                mean_motion_ddot=0.0,
                element_set_no=292,
                rev_at_epoch=6766,
            ),
        ),
    )


class TestSuppressDefaults:
    def test_suppress_defaults_true_omits_field_matching_spec_default(self):
        """suppress_defaults=True omits a field whose value equals FieldMetadata(spec_default=...)."""
        omm = _make_sgp4_omm(ephemeris_type=0)  # 0 == FieldMetadata(spec_default=0)
        output = _OMM_WRITER.write_string(
            omm, options=WriterOptions(suppress_defaults=True)
        )
        assert "EPHEMERIS_TYPE" not in output

    def test_suppress_defaults_true_keeps_field_not_matching_spec_default(self):
        """suppress_defaults=True still emits a field whose value differs from spec_default."""
        omm = _make_sgp4_omm(ephemeris_type=2)  # 2 != FieldMetadata(spec_default=0)
        output = _OMM_WRITER.write_string(
            omm, options=WriterOptions(suppress_defaults=True)
        )
        ephemeris_type_line = next(
            line for line in output.splitlines() if "EPHEMERIS_TYPE" in line
        )
        assert ephemeris_type_line.split("=")[1].strip() == "2"

    def test_suppress_defaults_false_emits_field_even_when_it_matches_spec_default(self):
        """Control case: the default suppress_defaults=False emits every non-None field."""
        omm = _make_sgp4_omm(ephemeris_type=0)
        output = _OMM_WRITER.write_string(
            omm, options=WriterOptions(suppress_defaults=False)
        )
        ephemeris_type_line = next(
            line for line in output.splitlines() if "EPHEMERIS_TYPE" in line
        )
        assert ephemeris_type_line.split("=")[1].strip() == "0"


_OCM_WRITER = KVNOCMWriter()


class TestIncludeUnits:
    @pytest.mark.xfail(
        reason=(
            "OPM/OMM KVN inline units are spec-optional (§7.7.1.1) but not yet implemented. "
            "This xfail covers OPM/OMM only; OEM and OCM data lines are separately tested below."
        ),
        strict=False,
    )
    def test_opm_kvn_with_include_units_true_emits_optional_inline_units_per_spec(self):
        """§7.7.1.1: OPM/OMM KVN may include [km] etc. after values; include_units=True should emit them."""
        opm = make_opm()
        opts = WriterOptions(include_units=True)
        output = _OPM_WRITER.write_string(opm, options=opts)
        x_lines = [line for line in output.splitlines() if line.strip().startswith("X ")]
        assert x_lines, "No 'X = ...' line found in output"
        x_line = x_lines[0]
        assert "[km]" in x_line, f"Expected [km] in X line but got: {x_line!r}"

    def test_include_units_false_has_no_units_in_output(self):
        """With include_units=False, no [unit] annotations in output (current baseline)."""
        opm = make_opm()
        opts = WriterOptions(include_units=False)
        output = _OPM_WRITER.write_string(opm, options=opts)
        lines_with_bracket_units = [
            line for line in output.splitlines() if "[km]" in line or "[km/s]" in line
        ]
        assert not lines_with_bracket_units

    def test_oem_kvn_ephemeris_data_lines_never_have_inline_units_regardless_of_option(
        self,
    ):
        """
        §7.7.2.1: OEM KVN ephemeris data lines must not display units — even with include_units=True.

        Spec quote: 'units shall be km, km/s, and km/s² ... but the units shall not be displayed.'
        """
        oem = make_oem(n_lines=3)
        for include in (True, False):
            output = _OEM_WRITER.write_string(
                oem, options=WriterOptions(include_units=include)
            )
            # Epoch-prefixed lines are the ephemeris data lines
            data_lines = [
                line
                for line in output.splitlines()
                if line.strip() and line.strip()[0].isdigit() and "T" in line.split()[0]
            ]
            assert data_lines, f"No data lines in OEM output (include_units={include})"
            for line in data_lines:
                assert "[" not in line, (
                    f"§7.7.2.1: inline unit in OEM ephemeris line (include_units={include}): {line!r}"
                )

    def test_oem_kvn_covariance_data_lines_never_have_inline_units(self):
        """§7.7.2.2: OEM KVN covariance data lines must not display units."""
        oem = read(FIXTURES / "oem_g13_covariance.kvn", fmt="kvn", message_type="oem")
        output = _OEM_WRITER.write_string(oem, options=WriterOptions(include_units=True))
        in_cov = False
        for line in output.splitlines():
            stripped = line.strip()
            if stripped == "COVARIANCE_START":
                in_cov = True
                continue
            if stripped == "COVARIANCE_STOP":
                in_cov = False
                continue
            if (
                in_cov
                and stripped
                and "=" not in stripped
                and not stripped.startswith("COMMENT")
            ):
                assert "[" not in stripped, (
                    f"§7.7.2.2: inline unit in OEM covariance data line: {stripped!r}"
                )

    def test_ocm_kvn_trajectory_data_lines_never_have_inline_units(self):
        """
        §7.7.3.5: OCM KVN trajectory data lines must not carry inline units.

        Units for OCM trajectory data go in the TRAJ_UNITS keyword, not inline.
        """
        ocm = OCM(
            header=OCM.Header(
                ccsds_ocm_vers="3.0", creation_date=CREATION_DATE, originator="TEST"
            ),
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
        output = _OCM_WRITER.write_string(ocm, options=WriterOptions(include_units=True))
        for line in output.splitlines():
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and "T" in stripped.split()[0]:
                assert "[" not in stripped, (
                    f"§7.7.3.5: inline unit in OCM trajectory data line: {stripped!r}"
                )

    def test_writer_options_are_frozen(self):
        """WriterOptions is immutable (frozen=True)."""
        opts = WriterOptions()
        with pytest.raises((AttributeError, TypeError)):
            opts.align_keywords = False  # type: ignore[misc]

    def test_writer_options_defaults(self):
        """Default WriterOptions values match the documented spec defaults."""
        opts = WriterOptions()
        assert opts.include_units is True
        assert opts.align_keywords is True
        assert opts.float_formats == {}
