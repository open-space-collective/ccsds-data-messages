"""
Unit tests for the XML parsing helpers (io/xml/parser.py).

Covers parse_xml_file / parse_xml_string and the namespace-agnostic element
helpers strip_ns, find_child, find_all, and get_text.
"""

from __future__ import annotations

from conftest import FIXTURES

from ccsds_data_messages.io.xml.parser import find_all
from ccsds_data_messages.io.xml.parser import find_child
from ccsds_data_messages.io.xml.parser import get_text
from ccsds_data_messages.io.xml.parser import parse_xml_file
from ccsds_data_messages.io.xml.parser import parse_xml_string
from ccsds_data_messages.io.xml.parser import strip_ns

_SAMPLE = (
    "<opm>"
    "<header><ORIGINATOR>TEST</ORIGINATOR><EMPTY>   </EMPTY></header>"
    "<body><item>a</item><item>b</item><blank/></body>"
    "</opm>"
)


class TestParse:
    def test_parse_xml_string_returns_root(self):
        root = parse_xml_string(_SAMPLE)
        assert strip_ns(root.tag) == "opm"

    def test_parse_xml_file_returns_root(self):
        # opm_g5.xml is a real ODM/XML spec fixture (Annex G5).
        root = parse_xml_file(FIXTURES / "opm_g5.xml")
        assert strip_ns(root.tag) == "opm"


class TestStripNs:
    def test_strips_clark_notation_prefix(self):
        assert strip_ns("{http://www.ccsds.org/schema/ndmxml}opm") == "opm"

    def test_leaves_unqualified_tag_unchanged(self):
        assert strip_ns("opm") == "opm"


class TestFindChild:
    def test_finds_direct_child(self):
        root = parse_xml_string(_SAMPLE)
        assert find_child(root, "header") is not None

    def test_missing_child_returns_none(self):
        root = parse_xml_string(_SAMPLE)
        assert find_child(root, "metadata") is None

    def test_none_parent_returns_none(self):
        # Enables safe chaining: find_child(find_child(root, "x"), "y")
        assert find_child(None, "header") is None


class TestFindAll:
    def test_returns_all_matching_children(self):
        body = find_child(parse_xml_string(_SAMPLE), "body")
        assert len(find_all(body, "item")) == 2

    def test_no_match_returns_empty_list(self):
        body = find_child(parse_xml_string(_SAMPLE), "body")
        assert find_all(body, "missing") == []

    def test_none_parent_returns_empty_list(self):
        assert find_all(None, "item") == []


class TestGetText:
    def test_returns_stripped_text(self):
        header = find_child(parse_xml_string(_SAMPLE), "header")
        assert get_text(find_child(header, "ORIGINATOR")) == "TEST"

    def test_whitespace_only_text_returns_default(self):
        header = find_child(parse_xml_string(_SAMPLE), "header")
        assert get_text(find_child(header, "EMPTY"), "fallback") == "fallback"

    def test_none_element_returns_default(self):
        assert not get_text(None)
        assert get_text(None, "d") == "d"
