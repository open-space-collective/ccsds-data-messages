"""
High-level API tests - read(), write(), read_string(), write_string(), type-specific functions.

Modules under test:
  src/ccsds_data_messages/io/reader.py
  src/ccsds_data_messages/io/writer.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FIXTURES, make_oem, make_omm, make_opm

from ccsds_data_messages import OCM, OEM, OMM, OPM, read, write
from ccsds_data_messages.exceptions import SpecViolationError
from ccsds_data_messages.io.reader import (
    read_ocm,
    read_oem,
    read_omm,
    read_opm,
    read_string,
)
from ccsds_data_messages.io.writer import write_string

# ---------------------------------------------------------------------------
# Happy paths - auto-detection from extension
# ---------------------------------------------------------------------------


class TestReadAutoDetect:
    def test_read_opm_from_kvn_extension(self):
        """read() infers KVN format and OPM type from .kvn filename."""
        fixture = FIXTURES / "opm_g1_simple.kvn"
        msg = read(fixture)
        assert isinstance(msg, OPM)

    def test_read_opm_from_xml_extension(self):
        """read() infers XML format and OPM type from .xml filename."""
        fixture = FIXTURES / "opm_g5.xml"
        msg = read(fixture)
        assert isinstance(msg, OPM)

    def test_read_omm_from_kvn_extension(self):
        fixture = FIXTURES / "omm_g7.kvn"
        msg = read(fixture)
        assert isinstance(msg, OMM)

    def test_read_oem_from_kvn_extension(self):
        fixture = FIXTURES / "oem_g11.kvn"
        msg = read(fixture)
        assert isinstance(msg, OEM)

    def test_read_ocm_from_kvn_extension(self):
        fixture = FIXTURES / "ocm_g15_minimal.kvn"
        msg = read(fixture)
        assert isinstance(msg, OCM)


# ---------------------------------------------------------------------------
# Happy paths - explicit format and message_type
# ---------------------------------------------------------------------------


class TestReadExplicit:
    def test_read_with_explicit_fmt_and_message_type(self):
        fixture = FIXTURES / "opm_g1_simple.kvn"
        msg = read(fixture, fmt="kvn", message_type="opm")
        assert isinstance(msg, OPM)

    def test_read_with_uppercase_fmt_and_type(self):
        """Format and message_type strings are normalized to lowercase."""
        fixture = FIXTURES / "opm_g1_simple.kvn"
        msg = read(fixture, fmt="KVN", message_type="OPM")
        assert isinstance(msg, OPM)


# ---------------------------------------------------------------------------
# read_string
# ---------------------------------------------------------------------------


class TestReadString:
    def test_read_string_kvn_opm_returns_opm(self, tmp_path: Path):
        opm = make_opm()
        path = tmp_path / "test.opm"
        write(opm, path)
        content = path.read_text()
        msg = read_string(content, fmt="kvn", message_type="opm")
        assert isinstance(msg, OPM)

    def test_read_string_kvn_omm_returns_omm(self, tmp_path: Path):
        omm = make_omm()
        path = tmp_path / "test.omm"
        write(omm, path)
        content = path.read_text()
        msg = read_string(content, fmt="kvn", message_type="omm")
        assert isinstance(msg, OMM)


# ---------------------------------------------------------------------------
# write / write_string
# ---------------------------------------------------------------------------


class TestWrite:
    def test_write_infers_kvn_format_from_extension(self, tmp_path: Path):
        """§7.3.6: first non-blank line of KVN must be the version keyword."""
        opm = make_opm()
        path = tmp_path / "out.opm"
        write(opm, path)
        content = path.read_text()
        first_line = next(line for line in content.splitlines() if line.strip())
        assert first_line.strip().startswith("CCSDS_OPM_VERS")

    def test_write_infers_xml_format_from_extension(self, tmp_path: Path):
        """XML output has an <opm ...> root element."""
        opm = make_opm()
        path = tmp_path / "out.xml"
        write(opm, path)
        content = path.read_text()
        assert "<opm" in content or "<OPM" in content

    def test_write_oem_kvn_contains_start_stop_markers(self, tmp_path: Path):
        """KVN OEM must contain META_START / META_STOP delimiters (§5.2)."""
        oem = make_oem()
        path = tmp_path / "out.oem"
        write(oem, path)
        content = path.read_text()
        assert "META_START" in content
        assert "META_STOP" in content

    def test_write_string_returns_str(self):
        opm = make_opm()
        result = write_string(opm, fmt="kvn")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_write_string_xml_returns_xml_content(self):
        opm = make_opm()
        result = write_string(opm, fmt="xml")
        assert isinstance(result, str)
        assert "<opm" in result or "<OPM" in result


# ---------------------------------------------------------------------------
# Type-specific read functions
# ---------------------------------------------------------------------------


class TestTypeSpecificRead:
    def test_read_opm_returns_opm_instance(self):
        fixture = FIXTURES / "opm_g1_simple.kvn"
        msg = read_opm(fixture)
        assert isinstance(msg, OPM)

    def test_read_omm_returns_omm_instance(self):
        fixture = FIXTURES / "omm_g7.kvn"
        msg = read_omm(fixture)
        assert isinstance(msg, OMM)

    def test_read_oem_returns_oem_instance(self):
        fixture = FIXTURES / "oem_g11.kvn"
        msg = read_oem(fixture)
        assert isinstance(msg, OEM)

    def test_read_ocm_returns_ocm_instance(self):
        fixture = FIXTURES / "ocm_g15_minimal.kvn"
        msg = read_ocm(fixture)
        assert isinstance(msg, OCM)

    def test_write_then_read_produces_equal_opm(self, tmp_path: Path):
        """OPM write → type-specific read → equal model."""
        opm = make_opm()
        path = tmp_path / "out.opm"
        write(opm, path)
        back = read_opm(path)
        assert isinstance(back, OPM)
        assert back.header.originator == opm.header.originator
        assert back.metadata.object_name == opm.metadata.object_name
        assert back.data.state_vector.x == pytest.approx(
            opm.data.state_vector.x, rel=1e-9
        )


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestReadErrors:
    def test_read_nonexistent_file_raises(self):
        # FileNotFoundError or CCSDSError - the file does not exist
        with pytest.raises((FileNotFoundError, OSError)):
            read(Path("_this_file_does_not_exist.opm"))

    def test_read_string_malformed_kvn_raises_spec_violation_error(self):
        # "THIS IS GARBAGE CONTENT" has no '=' on any line, so the KVN lexer
        # treats every line as an unrecognized data row (forward-compatible
        # skip) rather than raising ParseError - it never reaches OPM.Header
        # with any fields, so Pydantic validation fails with SpecViolationError.
        # ParseError is only raised by the OCM reader (STOP-without-START,
        # missing META block); OPM's flat KVN reader has no block structure to
        # violate, so ParseError is not reachable via this input for message_type="opm".
        with pytest.raises(SpecViolationError):
            read_string("THIS IS GARBAGE CONTENT", fmt="kvn", message_type="opm")

    def test_read_string_missing_mandatory_field_raises_spec_violation_error(
        self, tmp_path
    ):
        # Missing OBJECT_NAME in a syntactically valid KVN → SpecViolationError or similar
        broken_kvn = (
            "CCSDS_OPM_VERS = 3.0\n"
            "CREATION_DATE = 2020-001T12:00:00\n"
            "ORIGINATOR = TEST\n"
            # OBJECT_NAME is missing
            "OBJECT_ID = 2020-001A\n"
            "CENTER_NAME = EARTH\n"
            "REF_FRAME = GCRF\n"
            "TIME_SYSTEM = UTC\n"
            "EPOCH = 2020-001T00:00:00\n"
            "X = 7000.0 [km]\n"
            "Y = 0.0 [km]\n"
            "Z = 0.0 [km]\n"
            "X_DOT = 0.0 [km/s]\n"
            "Y_DOT = 7.5 [km/s]\n"
            "Z_DOT = 0.0 [km/s]\n"
        )
        with pytest.raises(SpecViolationError):
            read_string(broken_kvn, fmt="kvn", message_type="opm")

    def test_read_string_empty_content_raises_spec_violation_error(self):
        with pytest.raises(SpecViolationError):
            read_string("", fmt="kvn", message_type="opm")
