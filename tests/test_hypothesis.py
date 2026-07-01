"""
Property-based round-trip tests using Hypothesis.

Each test generates random valid domain model instances and verifies that
serializing then deserializing produces an equal model - covering both KVN
and XML formats for OPM, OMM, and OEM.

Run with:
    pip install hypothesis
    pytest tests/test_hypothesis.py -v

These tests are skipped automatically when hypothesis is not installed.
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip(
    "hypothesis", reason="hypothesis not installed - run `pip install hypothesis`"
)
hypothesis_pydantic = pytest.importorskip(
    "hypothesis.extra.pydantic", reason="hypothesis not installed"
)

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis.extra.pydantic import from_type  # noqa: E402

from ccsds_data_messages import (  # noqa: E402  # noqa: E402
    OCM,
    OEM,
    OMM,
    OPM,
    MessageFormat,
    MessageType,
    read_string,
    write_string,
)

# 25 examples is below the Hypothesis minimum for meaningful coverage of constrained schemas.
_SETTINGS = settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


@_SETTINGS
@given(from_type(OPM))
def test_opm_kvn_roundtrip(opm: OPM) -> None:
    content = write_string(opm, MessageFormat.KVN)
    assert read_string(content, MessageFormat.KVN, MessageType.OPM) == opm


@_SETTINGS
@given(from_type(OPM))
def test_opm_xml_roundtrip(opm: OPM) -> None:
    content = write_string(opm, MessageFormat.XML)
    assert read_string(content, MessageFormat.XML, MessageType.OPM) == opm


@_SETTINGS
@given(from_type(OMM))
def test_omm_kvn_roundtrip(omm: OMM) -> None:
    content = write_string(omm, MessageFormat.KVN)
    assert read_string(content, MessageFormat.KVN, MessageType.OMM) == omm


@_SETTINGS
@given(from_type(OMM))
def test_omm_xml_roundtrip(omm: OMM) -> None:
    content = write_string(omm, MessageFormat.XML)
    assert read_string(content, MessageFormat.XML, MessageType.OMM) == omm


@_SETTINGS
@given(from_type(OEM))
def test_oem_kvn_roundtrip(oem: OEM) -> None:
    content = write_string(oem, MessageFormat.KVN)
    assert read_string(content, MessageFormat.KVN, MessageType.OEM) == oem


@_SETTINGS
@given(from_type(OEM))
def test_oem_xml_roundtrip(oem: OEM) -> None:
    content = write_string(oem, MessageFormat.XML)
    assert read_string(content, MessageFormat.XML, MessageType.OEM) == oem


@_SETTINGS
@given(from_type(OCM))
def test_ocm_kvn_roundtrip(ocm: OCM) -> None:
    content = write_string(ocm, MessageFormat.KVN)
    assert read_string(content, MessageFormat.KVN, MessageType.OCM) == ocm


@pytest.mark.xfail(reason="OCM XML round-trip not yet fully supported", strict=True)
@_SETTINGS
@given(from_type(OCM))
def test_ocm_xml_roundtrip(ocm: OCM) -> None:
    content = write_string(ocm, MessageFormat.XML)
    assert read_string(content, MessageFormat.XML, MessageType.OCM) == ocm
