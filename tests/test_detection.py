"""Format and message-type detection tests."""

import pathlib
import tempfile

import pytest

from ccsds_data_messages.exceptions import DetectionError
from ccsds_data_messages.io.detection import detect_format, detect_message_type

KVN_OPM_HEADER = "CCSDS_OPM_VERS = 3.0\nORIGINATOR = TEST\n"
KVN_OEM_HEADER = "CCSDS_OEM_VERS = 3.0\nORIGINATOR = TEST\n"
KVN_OMM_HEADER = "CCSDS_OMM_VERS = 3.0\nORIGINATOR = TEST\n"
KVN_OCM_HEADER = "CCSDS_OCM_VERS = 3.0\nORIGINATOR = TEST\n"
XML_OPM_CONTENT = '<?xml version="1.0"?><opm id="CCSDS_OPM_VERS" version="3.0"></opm>'
XML_OEM_CONTENT = '<?xml version="1.0"?><oem id="CCSDS_OEM_VERS" version="3.0"></oem>'
XML_OMM_CONTENT = '<?xml version="1.0"?><omm id="CCSDS_OMM_VERS" version="3.0"></omm>'
XML_OCM_CONTENT = '<?xml version="1.0"?><ocm id="CCSDS_OCM_VERS" version="3.0"></ocm>'


def _write_temp(content: str, suffix: str, *, prefix: str | None = None) -> pathlib.Path:
    with tempfile.NamedTemporaryFile(
        encoding="utf-8", suffix=suffix, prefix=prefix, mode="w", delete=False
    ) as f:
        f.write(content)
    return pathlib.Path(f.name)


class TestDetectFormat:
    def test_xml_extension(self):
        p = _write_temp(KVN_OPM_HEADER, ".xml")
        try:
            assert detect_format(p) == "xml"
        finally:
            p.unlink()

    def test_kvn_extension_oem(self):
        p = _write_temp(KVN_OEM_HEADER, ".oem")
        try:
            assert detect_format(p) == "kvn"
        finally:
            p.unlink()

    def test_kvn_sniff_from_content(self):
        p = _write_temp(KVN_OPM_HEADER, ".txt")
        try:
            assert detect_format(p) == "kvn"
        finally:
            p.unlink()

    def test_xml_sniff_from_content(self):
        p = _write_temp(XML_OPM_CONTENT, ".txt")
        try:
            assert detect_format(p) == "xml"
        finally:
            p.unlink()


class TestDetectMessageType:
    def test_kvn_opm(self):
        p = _write_temp(KVN_OPM_HEADER, ".txt")
        try:
            assert detect_message_type(p, "kvn") == "opm"
        finally:
            p.unlink()

    def test_kvn_oem(self):
        p = _write_temp(KVN_OEM_HEADER, ".txt")
        try:
            assert detect_message_type(p, "kvn") == "oem"
        finally:
            p.unlink()

    def test_kvn_omm(self):
        p = _write_temp(KVN_OMM_HEADER, ".txt")
        try:
            assert detect_message_type(p, "kvn") == "omm"
        finally:
            p.unlink()

    def test_kvn_ocm(self):
        p = _write_temp(KVN_OCM_HEADER, ".txt")
        try:
            assert detect_message_type(p, "kvn") == "ocm"
        finally:
            p.unlink()

    def test_xml_opm(self):
        p = _write_temp(XML_OPM_CONTENT, ".txt")
        try:
            assert detect_message_type(p, "xml") == "opm"
        finally:
            p.unlink()

    def test_xml_oem(self):
        p = _write_temp(XML_OEM_CONTENT, ".txt")
        try:
            assert detect_message_type(p, "xml") == "oem"
        finally:
            p.unlink()

    def test_xml_omm(self):
        p = _write_temp(XML_OMM_CONTENT, ".txt")
        try:
            assert detect_message_type(p, "xml") == "omm"
        finally:
            p.unlink()

    def test_xml_ocm(self):
        p = _write_temp(XML_OCM_CONTENT, ".txt")
        try:
            assert detect_message_type(p, "xml") == "ocm"
        finally:
            p.unlink()

    def test_detect_message_type_empty_file_raises_detection_error(self):
        # An empty file has no version keyword → DetectionError
        p = _write_temp("", ".kvn")
        try:
            with pytest.raises(DetectionError):
                detect_message_type(p, "kvn")
        finally:
            p.unlink()

    def test_detect_message_type_unrecognized_header_keyword_raises_detection_error(self):
        # "CCSDS_XYZ_VERS = 3.0" is not a known message type keyword
        p = _write_temp("CCSDS_XYZ_VERS = 3.0\nORIGINATOR = TEST\n", ".kvn")
        try:
            with pytest.raises(DetectionError):
                detect_message_type(p, "kvn")
        finally:
            p.unlink()


class TestStemHints:
    """_STEM_HINTS: filename-stem keyword hint, checked before content sniffing."""

    def test_ephemeris_stem_hint_detects_oem(self):
        # Garbage content: if the stem hint didn't fire, content-sniffing would
        # find no version keyword and raise DetectionError.
        p = _write_temp("garbage, no version keyword", ".txt", prefix="ephemeris_")
        try:
            assert detect_message_type(p, "kvn") == "oem"
        finally:
            p.unlink()

    def test_comprehensive_stem_hint_detects_ocm(self):
        p = _write_temp("garbage, no version keyword", ".txt", prefix="comprehensive_")
        try:
            assert detect_message_type(p, "kvn") == "ocm"
        finally:
            p.unlink()

    def test_mean_stem_hint_detects_omm(self):
        p = _write_temp("garbage, no version keyword", ".txt", prefix="mean_")
        try:
            assert detect_message_type(p, "kvn") == "omm"
        finally:
            p.unlink()

    def test_parameter_stem_hint_detects_opm(self):
        p = _write_temp("garbage, no version keyword", ".txt", prefix="parameter_")
        try:
            assert detect_message_type(p, "kvn") == "opm"
        finally:
            p.unlink()

    def test_stem_hint_takes_precedence_over_content_sniffing(self):
        # Stem says "mean" (OMM), but the content is a well-formed OEM header -
        # the stem hint must win, proving the documented priority order
        # (extension, then stem hint, then content sniff).
        p = _write_temp(KVN_OEM_HEADER, ".txt", prefix="mean_")
        try:
            assert detect_message_type(p, "kvn") == "omm"
        finally:
            p.unlink()


class TestDetectFormatEdgeCases:
    def test_detect_format_dat_extension_with_kvn_content_detected_as_kvn(self):
        # Content sniff fallback: .dat file with KVN header → KVN
        p = _write_temp(KVN_OPM_HEADER, ".dat")
        try:
            assert detect_format(p) == "kvn"
        finally:
            p.unlink()

    def test_detect_format_dat_extension_with_xml_content_detected_as_xml(self):
        # Content sniff fallback: .dat file with XML <opm ...> → XML
        p = _write_temp(XML_OPM_CONTENT, ".dat")
        try:
            assert detect_format(p) == "xml"
        finally:
            p.unlink()
