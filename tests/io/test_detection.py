"""Format and message-type detection tests."""

import pathlib

import pytest

from ccsds_data_messages.exceptions import DetectionError
from ccsds_data_messages.io.detection import detect_format
from ccsds_data_messages.io.detection import detect_message_type

KVN_OPM_HEADER = "CCSDS_OPM_VERS = 3.0\nORIGINATOR = TEST\n"
KVN_OEM_HEADER = "CCSDS_OEM_VERS = 3.0\nORIGINATOR = TEST\n"
KVN_OMM_HEADER = "CCSDS_OMM_VERS = 3.0\nORIGINATOR = TEST\n"
KVN_OCM_HEADER = "CCSDS_OCM_VERS = 3.0\nORIGINATOR = TEST\n"
XML_OPM_CONTENT = '<?xml version="1.0"?><opm id="CCSDS_OPM_VERS" version="3.0"></opm>'
XML_OEM_CONTENT = '<?xml version="1.0"?><oem id="CCSDS_OEM_VERS" version="3.0"></oem>'
XML_OMM_CONTENT = '<?xml version="1.0"?><omm id="CCSDS_OMM_VERS" version="3.0"></omm>'
XML_OCM_CONTENT = '<?xml version="1.0"?><ocm id="CCSDS_OCM_VERS" version="3.0"></ocm>'


def _write(directory: pathlib.Path, name: str, content: str) -> pathlib.Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class TestDetectFormat:
    def test_xml_extension(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.xml", KVN_OPM_HEADER)
        assert detect_format(p) == "xml"

    def test_kvn_extension_oem(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.oem", KVN_OEM_HEADER)
        assert detect_format(p) == "kvn"

    def test_kvn_sniff_from_content(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", KVN_OPM_HEADER)
        assert detect_format(p) == "kvn"

    def test_xml_sniff_from_content(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", XML_OPM_CONTENT)
        assert detect_format(p) == "xml"


class TestDetectMessageType:
    def test_kvn_opm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", KVN_OPM_HEADER)
        assert detect_message_type(p, "kvn") == "opm"

    def test_kvn_oem(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", KVN_OEM_HEADER)
        assert detect_message_type(p, "kvn") == "oem"

    def test_kvn_omm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", KVN_OMM_HEADER)
        assert detect_message_type(p, "kvn") == "omm"

    def test_kvn_ocm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", KVN_OCM_HEADER)
        assert detect_message_type(p, "kvn") == "ocm"

    def test_xml_opm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", XML_OPM_CONTENT)
        assert detect_message_type(p, "xml") == "opm"

    def test_xml_oem(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", XML_OEM_CONTENT)
        assert detect_message_type(p, "xml") == "oem"

    def test_xml_omm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", XML_OMM_CONTENT)
        assert detect_message_type(p, "xml") == "omm"

    def test_xml_ocm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "msg.txt", XML_OCM_CONTENT)
        assert detect_message_type(p, "xml") == "ocm"

    def test_detect_message_type_empty_file_raises_detection_error(
        self, tmp_path: pathlib.Path
    ):
        # An empty file has no version keyword, so detection raises DetectionError
        p = _write(tmp_path, "msg.kvn", "")
        with pytest.raises(DetectionError):
            detect_message_type(p, "kvn")

    def test_detect_message_type_unrecognized_header_keyword_raises_detection_error(
        self, tmp_path: pathlib.Path
    ):
        # "CCSDS_XYZ_VERS = 3.0" is not a known message type keyword
        p = _write(tmp_path, "msg.kvn", "CCSDS_XYZ_VERS = 3.0\nORIGINATOR = TEST\n")
        with pytest.raises(DetectionError):
            detect_message_type(p, "kvn")

    def test_detect_message_type_xml_non_odm_root_raises_detection_error(
        self, tmp_path: pathlib.Path
    ):
        # An XML document whose root is not one of the ODM types (opm/omm/oem/ocm)
        # cannot be identified: _sniff_xml_type finds no match and detection fails.
        p = _write(
            tmp_path, "msg.xml", "<?xml version='1.0'?>\n<foo><bar>1</bar></foo>\n"
        )
        with pytest.raises(DetectionError):
            detect_message_type(p, "xml")


class TestStemHints:
    """_STEM_HINTS: filename-stem keyword hint, checked before content sniffing."""

    def test_ephemeris_stem_hint_detects_oem(self, tmp_path: pathlib.Path):
        # Garbage content: if the stem hint didn't fire, content-sniffing would
        # find no version keyword and raise DetectionError.
        p = _write(tmp_path, "ephemeris_msg.txt", "garbage, no version keyword")
        assert detect_message_type(p, "kvn") == "oem"

    def test_comprehensive_stem_hint_detects_ocm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "comprehensive_msg.txt", "garbage, no version keyword")
        assert detect_message_type(p, "kvn") == "ocm"

    def test_mean_stem_hint_detects_omm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "mean_msg.txt", "garbage, no version keyword")
        assert detect_message_type(p, "kvn") == "omm"

    def test_parameter_stem_hint_detects_opm(self, tmp_path: pathlib.Path):
        p = _write(tmp_path, "parameter_msg.txt", "garbage, no version keyword")
        assert detect_message_type(p, "kvn") == "opm"

    def test_stem_hint_takes_precedence_over_content_sniffing(
        self, tmp_path: pathlib.Path
    ):
        # Stem says "mean" (OMM), but the content is a well-formed OEM header -
        # the stem hint must win, proving the documented priority order
        # (extension, then stem hint, then content sniff).
        p = _write(tmp_path, "mean_msg.txt", KVN_OEM_HEADER)
        assert detect_message_type(p, "kvn") == "omm"


class TestDetectFormatEdgeCases:
    def test_detect_format_dat_extension_with_kvn_content_detected_as_kvn(
        self, tmp_path: pathlib.Path
    ):
        # Content sniff fallback: .dat file with a KVN header is detected as KVN
        p = _write(tmp_path, "msg.dat", KVN_OPM_HEADER)
        assert detect_format(p) == "kvn"

    def test_detect_format_dat_extension_with_xml_content_detected_as_xml(
        self, tmp_path: pathlib.Path
    ):
        # Content sniff fallback: .dat file with an XML <opm ...> is detected as XML
        p = _write(tmp_path, "msg.dat", XML_OPM_CONTENT)
        assert detect_format(p) == "xml"
