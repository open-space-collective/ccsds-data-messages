"""
Shared BaseHeader field round-trip tests - classification, message_id.

Module under test: src/ccsds_data_messages/models/_base.py

Parametrized across all four message types to avoid 4x duplication (each
message type's KVN reader/writer pair is otherwise exercised independently
in test_opm.py/test_omm.py/test_oem.py/test_ocm.py).
"""

from __future__ import annotations

import pytest
from conftest import make_ocm, make_oem, make_omm, make_opm

from ccsds_data_messages.io.kvn.ocm_reader import KVNOCMReader
from ccsds_data_messages.io.kvn.ocm_writer import KVNOCMWriter
from ccsds_data_messages.io.kvn.oem_reader import KVNOEMReader
from ccsds_data_messages.io.kvn.oem_writer import KVNOEMWriter
from ccsds_data_messages.io.kvn.omm_reader import KVNOMMReader
from ccsds_data_messages.io.kvn.omm_writer import KVNOMMWriter
from ccsds_data_messages.io.kvn.opm_reader import KVNOPMReader
from ccsds_data_messages.io.kvn.opm_writer import KVNOPMWriter

_MESSAGE_TYPES = [
    ("opm", make_opm, KVNOPMReader(), KVNOPMWriter()),
    ("omm", make_omm, KVNOMMReader(), KVNOMMWriter()),
    ("oem", make_oem, KVNOEMReader(), KVNOEMWriter()),
    ("ocm", make_ocm, KVNOCMReader(), KVNOCMWriter()),
]


@pytest.mark.parametrize(
    ("name", "make", "reader", "writer"),
    _MESSAGE_TYPES,
    ids=[t[0] for t in _MESSAGE_TYPES],
)
def test_classification_round_trips_through_kvn(name, make, reader, writer):
    msg = make(header={"classification": "UNCLASSIFIED // FOR OFFICIAL USE ONLY"})
    content = writer.write_string(msg)
    assert "CLASSIFICATION" in content
    back = reader.read_string(content)
    assert back.header.classification == "UNCLASSIFIED // FOR OFFICIAL USE ONLY"


@pytest.mark.parametrize(
    ("name", "make", "reader", "writer"),
    _MESSAGE_TYPES,
    ids=[t[0] for t in _MESSAGE_TYPES],
)
def test_message_id_round_trips_through_kvn(name, make, reader, writer):
    msg = make(header={"message_id": "MSG-2024-001"})
    content = writer.write_string(msg)
    assert "MESSAGE_ID" in content
    back = reader.read_string(content)
    assert back.header.message_id == "MSG-2024-001"
