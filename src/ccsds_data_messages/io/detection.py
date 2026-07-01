# SPDX-License-Identifier: Apache-2.0

"""
Format/message-type detection for auto-detecting a file's KVN/XML format and OPM/OMM/OEM/OCM type.

Spec references:
- Section 7.3.5: Blank lines may be ignored.
- Section 7.3.6: The first header line is the first non-blank line.
- Section 7.9.1: KVN version keywords: ``CCSDS_OPM_VERS``, ``CCSDS_OMM_VERS``, ``CCSDS_OEM_VERS``, ``CCSDS_OCM_VERS``.
- Section 8.2: First line of an XML file: ``<?xml version="1.0" encoding="UTF-8"?>``.
- Section 8.3.2: XML root element tags: ``<opm>``, ``<omm>``, ``<oem>``, ``<ocm>``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ccsds_data_messages.exceptions import DetectionError
from ccsds_data_messages.io.format import MessageFormat, MessageType

if TYPE_CHECKING:
    from pathlib import Path

_ODM_TYPES: frozenset[str] = frozenset(MessageType)

_XML_TAG_RE: re.Pattern[str] = re.compile(r"<([a-z]+)[\s>/]")  # section 8.3.2
_KVN_VERS_RE: re.Pattern[str] = re.compile(
    r"CCSDS_(OEM|OMM|OPM|OCM)_VERS"
)  # section 7.9.1

_STEM_HINTS: dict[str, MessageType] = {
    "ephemeris": MessageType.OEM,
    "comprehensive": MessageType.OCM,
    "mean": MessageType.OMM,
    "parameter": MessageType.OPM,
}


def _first_nonblank_line(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            if stripped := line.strip():
                return stripped
    return ""


def _sniff_kvn_type(path: Path) -> MessageType | None:
    match: re.Match[str] | None = _KVN_VERS_RE.match(_first_nonblank_line(path))
    return MessageType(match.group(1).lower()) if match else None


def _sniff_xml_type(path: Path) -> MessageType | None:
    with path.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            for match in _XML_TAG_RE.finditer(line):
                if (tag := match.group(1)) in _ODM_TYPES:
                    return MessageType(tag)
    return None


def detect_format(path: Path) -> MessageFormat:
    if (suffix := path.suffix.lower()) == ".xml":
        return MessageFormat.XML
    if suffix[1:] in _ODM_TYPES:
        return MessageFormat.KVN
    first: str = _first_nonblank_line(path)
    if first.startswith("<"):
        return MessageFormat.XML
    return MessageFormat.KVN


def detect_message_type(
    path: Path,
    fmt: MessageFormat | str,
) -> MessageType:
    """
    Return the CCSDS data message type for ``path``.

    Args:
        path (Path): The path to the file to detect the format of.
        fmt (MessageFormat | str): The format to detect the message type of.

    Returns:
        MessageType: The CCSDS data message type.

    Raises:
        DetectionError: if the type cannot be determined.
    """
    if (message_type := path.suffix.lower()[1:]) in _ODM_TYPES:
        return MessageType(message_type)

    stem: str = path.stem.lower()
    for keyword, hint in _STEM_HINTS.items():
        if keyword in stem:
            return hint

    sniffed: MessageType | None = (
        _sniff_kvn_type(path)
        if fmt == MessageFormat.KVN
        else _sniff_xml_type(path)
        if fmt == MessageFormat.XML
        else None
    )
    if sniffed is not None:
        return sniffed

    raise DetectionError(
        f"Cannot determine the CCSDS data message type for {path.name!r}. "
        f"Rename the file with a standard extension (.oem, .omm, .opm, .ocm, .xml), "
        f"include a standard ODM version keyword (§7.9.1), "
        f"or pass ``message_type=`` explicitly."
    )
