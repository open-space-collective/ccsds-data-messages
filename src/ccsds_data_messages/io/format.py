# SPDX-License-Identifier: Apache-2.0

"""
Format and message-type identifiers used across the io package.

``MessageFormat`` and ``MessageType`` together key the reader/writer registry
(``io/registry.py``) and are the values ``read()``/``write()`` accept for their
``fmt``/``message_type`` parameters, either as these enum members or as their
plain-string equivalents (e.g. ``"kvn"``, ``"oem"``).
"""

from __future__ import annotations

from enum import StrEnum


class MessageFormat(StrEnum):
    KVN = "kvn"
    XML = "xml"


class MessageType(StrEnum):
    OEM = "oem"
    OMM = "omm"
    OPM = "opm"
    OCM = "ocm"
