"""
Spec references:
    - section 7.3.5: Blank lines may be ignored.
    - section 7.3.6: The first header line is the first non-blank line.
    - section 7.9.1: KVN version keywords: ``CCSDS_OPM_VERS``, ``CCSDS_OMM_VERS``,
            ``CCSDS_OEM_VERS``, ``CCSDS_OCM_VERS``.
    - section 8.2: First line of an XML file: ``<?xml version="1.0" encoding="UTF-8">``.
    - section 8.3.2: XML root element tags: ``<opm>``, ``<omm>``, ``<oem>``, ``<ocm>``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

_MessageType = Literal["oem", "omm", "opm", "ocm"]

_ODM_TYPES: frozenset[str] = frozenset({"oem", "omm", "opm", "ocm"})

_XML_TAG_RE: re.Pattern[str] = re.compile(r"<([a-z]+)[\s>/]")               # section 8.3.2
_KVN_VERS_RE: re.Pattern[str] = re.compile(r"CCSDS_(OEM|OMM|OPM|OCM)_VERS") # section 7.9.1

_STEM_HINTS: dict[str, _MessageType] = {
    "ephemeris": "oem",
    "comprehensive": "ocm",
    "mean": "omm",
    "parameter": "opm",
}


def _first_nonblank_line(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                return stripped
    return ""


def _sniff_kvn_type(path: Path) -> _MessageType | None:
    m: re.Match[str] | None = _KVN_VERS_RE.match(_first_nonblank_line(path))
    return m.group(1).lower() if m else None  # type: ignore[return-value]


def _sniff_xml_type(path: Path) -> _MessageType | None:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for m in _XML_TAG_RE.finditer(line):
                if (tag := m.group(1)) in _ODM_TYPES:
                    return tag  # type: ignore[return-value]
    return None


def detect_format(path: Path) -> Literal["kvn", "xml"]:
    """
    Return ``'kvn'`` or ``'xml'`` for path.
    """
    suffix: str = path.suffix.lower()
    if suffix == ".xml":
        return "xml"
    if suffix[1:] in _ODM_TYPES:
        return "kvn"
    first: str = _first_nonblank_line(path)
    if first.startswith("<"):
        return "xml"
    return "kvn"


def detect_message_type(path: Path, fmt: str) -> _MessageType:
    """
    Return the CCSDS message type for ``path``.

    Raises:
        ValueError: if the type cannot be determined.
    """
    msg_type: str = path.suffix.lower()[1:]
    if msg_type in _ODM_TYPES:
        return msg_type  # type: ignore[return-value]

    stem: str = path.stem.lower()
    for keyword, hint in _STEM_HINTS.items():
        if keyword in stem:
            return hint

    sniffed: _MessageType | None = _sniff_kvn_type(path) if fmt == "kvn" else _sniff_xml_type(path) if fmt == "xml" else None
    if sniffed is not None:
        return sniffed

    raise ValueError(
        f"Cannot determine the CCSDS message type for ``{path.name}``. "
        f"Rename the file with a standard extension (``.oem``, ``.omm``, ``.opm``, ``.ocm``, ``.xml``), "
        f"include a standard ODM version keyword (§7.9.1), "
        f"or pass ``message_type=`` explicitly."
    )
