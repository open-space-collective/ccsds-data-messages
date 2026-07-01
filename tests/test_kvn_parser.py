"""
Unit tests for the KVN lexer (io/kvn/parser.py).

Covers all six line types: BlankLine, CommentLine, KeyValueLine,
BlockStartLine, BlockStopLine, DataLine.
"""

from __future__ import annotations

import warnings

import pytest

from ccsds_data_messages.io.kvn.parser import (
    BlankLine,
    BlockStartLine,
    BlockStopLine,
    CommentLine,
    DataLine,
    KeyValueLine,
    parse_kvn,
)


def test_parse_kvn_blank_line():
    lines = parse_kvn("   ")
    assert lines == [BlankLine()]


def test_parse_kvn_comment_line():
    lines = parse_kvn("COMMENT hello world")
    assert lines == [CommentLine(text="hello world")]


def test_parse_kvn_kv_line_strips_units():
    lines = parse_kvn("X = 6503.514000 [km]")
    assert lines == [KeyValueLine(keyword="X", value="6503.514000")]


def test_parse_kvn_kv_line_no_units():
    lines = parse_kvn("CCSDS_OPM_VERS = 3.0")
    assert lines == [KeyValueLine(keyword="CCSDS_OPM_VERS", value="3.0")]


def test_parse_kvn_block_start():
    lines = parse_kvn("META_START")
    assert lines == [BlockStartLine(block_name="META")]


def test_parse_kvn_block_stop():
    lines = parse_kvn("META_STOP")
    assert lines == [BlockStopLine(block_name="META")]


def test_parse_kvn_data_line():
    lines = parse_kvn("2020-001T00:00:00.000 7000.0 100.0 200.0 0.5 7.5 0.1")
    assert lines == [
        DataLine(text="2020-001T00:00:00.000 7000.0 100.0 200.0 0.5 7.5 0.1")
    ]


def test_parse_kvn_multiline():
    text = "CCSDS_OPM_VERS = 3.0\nCREATION_DATE = 2022-11-06T09:23:57\n"
    lines = parse_kvn(text)
    assert lines == [
        KeyValueLine(keyword="CCSDS_OPM_VERS", value="3.0"),
        KeyValueLine(keyword="CREATION_DATE", value="2022-11-06T09:23:57"),
    ]


# ---------------------------------------------------------------------------
# New edge-case and negative tests
# ---------------------------------------------------------------------------


def test_parse_kvn_kv_line_extra_whitespace_around_equals():
    # §7.4.5-7.4.6: whitespace around '=' is not significant
    lines = parse_kvn("X   =   6503.0 [km]")
    assert lines == [KeyValueLine(keyword="X", value="6503.0")]


def test_parse_kvn_covariance_start_block():
    # COVARIANCE_START is a valid block delimiter in OPM/OEM (§3.2.4.10)
    lines = parse_kvn("COVARIANCE_START")
    assert lines == [BlockStartLine(block_name="COVARIANCE")]


def test_parse_kvn_covariance_stop_block():
    lines = parse_kvn("COVARIANCE_STOP")
    assert lines == [BlockStopLine(block_name="COVARIANCE")]


def test_parse_kvn_ephemeris_data_start_block():
    # EPHEMERIS_DATA_START is a valid block delimiter in OEM
    lines = parse_kvn("EPHEMERIS_DATA_START")
    assert lines == [BlockStartLine(block_name="EPHEMERIS_DATA")]


def test_parse_kvn_blank_line_in_sequence():
    # §7.3.5: blank lines may appear anywhere in a KVN document
    text = "CCSDS_OPM_VERS = 3.0\n\nCREATION_DATE = 2022-11-06T09:23:57\n"
    lines = parse_kvn(text)
    assert BlankLine() in lines
    assert KeyValueLine(keyword="CCSDS_OPM_VERS", value="3.0") in lines
    assert KeyValueLine(keyword="CREATION_DATE", value="2022-11-06T09:23:57") in lines


# ---------------------------------------------------------------------------
# Diagnostic warnings - malformed-but-tolerated input (§7.3.2, 7.3.4, 7.4.4, 7.8.5)
# ---------------------------------------------------------------------------


def test_parse_kvn_bare_comment_warns_and_falls_through_to_data_line():
    # §7.8.5: COMMENT must be followed by at least one space
    with pytest.warns(UserWarning, match="Bare 'COMMENT' line"):
        lines = parse_kvn("COMMENT")
    assert lines == [DataLine(text="COMMENT")]


def test_parse_kvn_mixed_case_keyword_warns_and_falls_through_to_data_line():
    # §7.4.4: keywords must be uppercase
    with pytest.warns(UserWarning, match="non-uppercase keyword"):
        lines = parse_kvn("Object_Name = TESTSAT")
    assert lines == [DataLine(text="Object_Name = TESTSAT")]


def test_parse_kvn_line_exceeding_max_length_warns():
    # §7.3.2: line-length limit is opt-in via max_line_length
    long_line = "X = " + "1" * 300
    with pytest.warns(UserWarning, match="exceeding the 254-character limit"):
        parse_kvn(long_line, max_line_length=254)


def test_parse_kvn_no_max_line_length_never_warns_on_long_line():
    # Default (max_line_length=None) is for formats with no limit, e.g. OCM (§7.3.3)
    long_line = "X = " + "1" * 300
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        parse_kvn(long_line)  # must not raise/warn


def test_parse_kvn_non_printable_ascii_warns():
    # §7.3.4: only printable ASCII and blanks are permitted
    with pytest.warns(UserWarning, match="non-printable-ASCII or control characters"):
        parse_kvn("X = 1.0\x01")
