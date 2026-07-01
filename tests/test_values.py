"""
Public re-export smoke test.

Module under test: src/ccsds_data_messages/values.py
"""

from __future__ import annotations

import ccsds_data_messages.values as public_values
from ccsds_data_messages.models import values as internal_values


def test_values_reexports_match_models_values():
    for name in public_values.__all__:
        assert getattr(public_values, name) is getattr(internal_values, name)
