"""
Tests for the CCSDSDataMessage abstract base's instantiation guard.

Module under test: src/ccsds_data_messages/models/message.py
"""

from __future__ import annotations

import pytest
from conftest import make_opm

from ccsds_data_messages import CCSDSDataMessage


def test_ccsds_data_message_direct_instantiation_raises_type_error():
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        CCSDSDataMessage()


def test_concrete_subclass_instantiation_is_not_blocked():
    # The __new__ guard only fires for CCSDSDataMessage itself; concrete
    # subclasses must remain constructible.
    assert isinstance(make_opm(), CCSDSDataMessage)
