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
