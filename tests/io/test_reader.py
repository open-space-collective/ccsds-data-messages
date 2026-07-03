"""
Reader-side high-level API tests.

Covers read() auto-detection and explicit format/type, read_string(), the
type-specific read functions (read_opm/read_omm/read_oem/read_ocm), and read
error paths.

Modules under test:
  src/ccsds_data_messages/io/reader.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FIXTURES
from conftest import make_omm
from conftest import make_opm

from ccsds_data_messages import OCM
from ccsds_data_messages import OEM
from ccsds_data_messages import OMM
from ccsds_data_messages import OPM
from ccsds_data_messages import read
from ccsds_data_messages import write
from ccsds_data_messages.exceptions import DetectionError
from ccsds_data_messages.exceptions import SpecViolationError
from ccsds_data_messages.io.reader import read_ocm
from ccsds_data_messages.io.reader import read_oem
from ccsds_data_messages.io.reader import read_omm
from ccsds_data_messages.io.reader import read_opm
from ccsds_data_messages.io.reader import read_string


class TestReadAutoDetection:
    def test_read_opm_from_kvn_extension(self):
        """read() infers KVN format and OPM type from .kvn filename."""
        fixture = FIXTURES / "opm_g1_simple.kvn"
        msg: OPM = read(fixture)
        assert isinstance(msg, OPM)

    def test_read_opm_from_xml_extension(self):
        """read() infers XML format and OPM type from .xml filename."""
        fixture = FIXTURES / "opm_g5.xml"
        msg: OPM = read(fixture)
        assert isinstance(msg, OPM)

    def test_read_omm_from_kvn_extension(self):
        fixture = FIXTURES / "omm_g7.kvn"
        msg: OMM = read(fixture)
        assert isinstance(msg, OMM)

    def test_read_oem_from_kvn_extension(self):
        fixture = FIXTURES / "oem_g11.kvn"
        msg: OEM = read(fixture)
        assert isinstance(msg, OEM)

    def test_read_ocm_from_kvn_extension(self):
        fixture = FIXTURES / "ocm_g15_minimal.kvn"
        msg: OCM = read(fixture)
        assert isinstance(msg, OCM)

    def test_read_unknown_extension_raises_value_error(self):
        fixture = FIXTURES / "unknown.txt"
        with pytest.raises(DetectionError):
            read(fixture)


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
        """OPM write, then type-specific read, yields an equal model."""
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
        # Missing OBJECT_NAME in a syntactically valid KVN raises SpecViolationError or similar
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
