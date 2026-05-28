"""
Format and message-type detection for CCSDS Orbit Data Messages.

Two orthogonal questions are answered independently:

  detect_format(path)            → 'kvn' | 'xml'
  detect_message_type(path, fmt) → 'oem' | 'omm' | 'opm' | 'ocm'

Detection is pure: no side effects beyond reading the minimum necessary
bytes from the file.  No imports from models/, compute/, or adapters.

Spec references
---------------
§7.3.5  Blank lines have no assignable meaning and may be ignored.
§7.3.6  The first header line must be the first non-blank line in the file.
§7.9.1  KVN version keywords: CCSDS_OPM_VERS, CCSDS_OMM_VERS,
        CCSDS_OEM_VERS, CCSDS_OCM_VERS.
§8.2    First line of an XML instantiation: <?xml version="1.0" encoding="UTF-8">
§8.3.2  XML root element tags: <opm>, <omm>, <oem>, <ocm>.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Static look-up tables (no model imports)
# ---------------------------------------------------------------------------

# File extension → message type (unambiguous).
_EXT_TO_TYPE: dict[str, Literal["oem", "omm", "opm", "ocm"]] = {
    ".oem": "oem",
    ".omm": "omm",
    ".opm": "opm",
    ".ocm": "ocm",
}

# §7.9.1 — KVN version keyword prefix → message type.
_KVN_VERSION_PREFIX_TO_TYPE: dict[str, Literal["oem", "omm", "opm", "ocm"]] = {
    "CCSDS_OEM_VERS": "oem",
    "CCSDS_OMM_VERS": "omm",
    "CCSDS_OPM_VERS": "opm",
    "CCSDS_OCM_VERS": "ocm",
}

# §8.3.2 — XML root element tag name → message type.
_XML_TAG_TO_TYPE: dict[str, Literal["oem", "omm", "opm", "ocm"]] = {
    "oem": "oem",
    "omm": "omm",
    "opm": "opm",
    "ocm": "ocm",
}

# Filename stem keywords as a fallback heuristic (case-insensitive substring).
_STEM_HINTS: list[tuple[str, Literal["oem", "omm", "opm", "ocm"]]] = [
    ("ephemeris",    "oem"),
    ("comprehensive","ocm"),
    ("mean",         "omm"),
    ("parameter",    "opm"),
]

# §8.3.2 — regex to extract the first XML element tag name.
# Skips the XML declaration (<?xml ...?>) because '?' is not in [a-z].
_XML_TAG_RE = re.compile(r"<([a-z]+)[\s>/]")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _first_nonblank_line(path: Path) -> str:
    """
    Return the first non-blank line from path, stripped of surrounding
    whitespace.

    §7.3.5 — blank lines are ignorable.
    §7.3.6 — the first header line is the first non-blank line.
    Reads only until the first non-blank line to minimise I/O.
    """
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                return stripped
    return ""


def _sniff_kvn_type(
    path: Path,
) -> Literal["oem", "omm", "opm", "ocm"] | None:
    """
    Detect message type from the KVN version keyword on the first line.

    §7.3.6 — first non-blank line is the version keyword line.
    §7.9.1 — version keyword prefix uniquely identifies the message type.
    """
    first = _first_nonblank_line(path)
    for prefix, msg_type in _KVN_VERSION_PREFIX_TO_TYPE.items():
        if first.startswith(prefix):
            return msg_type
    return None


def _sniff_xml_type(
    path: Path,
) -> Literal["oem", "omm", "opm", "ocm"] | None:
    """
    Detect message type from the XML root element tag.

    §8.2  — first line is the XML declaration (<?xml …?>).
    §8.3.2 — root element tag name is opm | omm | oem | ocm.
    Reads the minimum number of lines needed to find the root tag.
    """
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for m in _XML_TAG_RE.finditer(line):
                tag = m.group(1)
                if tag in _XML_TAG_TO_TYPE:
                    return _XML_TAG_TO_TYPE[tag]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_format(path: Path) -> Literal["kvn", "xml"]:
    """
    Return the file format: 'kvn' or 'xml'.

    Detection priority
    ------------------
    1. File extension — .xml → 'xml'; .oem/.omm/.opm/.ocm → 'kvn'.
    2. Content sniff — first non-blank line:
       - Starts with '<'          → 'xml'  (§8.2: XML declaration / root tag)
       - Starts with 'CCSDS_'    → 'kvn'  (§7.3.6: version keyword)
    3. Default fallback           → 'kvn'

    Never raises on a valid file.
    """
    suffix = path.suffix.lower()

    # 1. Extension — unambiguous.
    if suffix == ".xml":
        return "xml"
    if suffix in _EXT_TO_TYPE:
        return "kvn"

    # 2. Content sniff (§7.3.6 for KVN first line; §8.2 for XML first line).
    first = _first_nonblank_line(path)
    if first.startswith("<"):
        return "xml"
    if first.startswith("CCSDS_"):
        return "kvn"

    # 3. Fallback — KVN is the more common plain-text format.
    return "kvn"


def detect_message_type(
    path: Path,
    fmt: str,
) -> Literal["oem", "omm", "opm", "ocm"]:
    """
    Return the CCSDS message type: 'oem', 'omm', 'opm', or 'ocm'.

    Detection priority
    ------------------
    1. File extension — .oem/.omm/.opm/.ocm.
    2. Filename stem keyword heuristic (case-insensitive substring):
       'ephemeris' → oem, 'comprehensive' → ocm,
       'mean'      → omm, 'parameter'     → opm.
    3. Content sniff:
       - KVN: §7.3.6 first non-blank line is the version keyword (§7.9.1).
       - XML: §8.3.2 root element tag name.

    Raises
    ------
    ValueError
        If the type cannot be determined from any of the above sources.
        Pass an explicit message_type= argument to Reader.read() to bypass.
    """
    # 1. Extension.
    suffix = path.suffix.lower()
    if suffix in _EXT_TO_TYPE:
        return _EXT_TO_TYPE[suffix]

    # 2. Stem keyword heuristic.
    stem = path.stem.lower()
    for keyword, msg_type in _STEM_HINTS:
        if keyword in stem:
            return msg_type

    # 3. Content sniff.
    sniffed: Literal["oem", "omm", "opm", "ocm"] | None
    if fmt == "kvn":
        sniffed = _sniff_kvn_type(path)
    elif fmt == "xml":
        sniffed = _sniff_xml_type(path)
    else:
        sniffed = None

    if sniffed is not None:
        return sniffed

    raise ValueError(
        f"Cannot determine the CCSDS message type for '{path.name}'. "
        f"Rename the file with a standard extension (.oem, .omm, .opm, .ocm, "
        f".xml), include a standard ODM version keyword on the first line "
        f"(§7.3.6/§7.9.1), or pass an explicit message_type= argument."
    )
