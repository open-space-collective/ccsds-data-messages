"""
Wraps ElementTree parsing and isolates all namespace handling in one place.

Returns Element objects: no domain types.  All namespace-stripping logic
lives here; adapters must not implement it themselves.

Spec references:
- Section 8.1: ODM keyword tags appear in all capitals; structural tags in lowerCamelCase.
- Section 8.2: First line: <?xml version="1.0" encoding="UTF-8"?>
- Section 8.3.3: xmlns:xsi namespace attribute on root element.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import defusedxml.ElementTree as DefusedET

from ccsds_data_messages.exceptions import ParseError

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET
    from pathlib import Path


def parse_xml_file(path: Path) -> ET.Element:
    """
    Parse an ODM/XML file and return the root ``ET.Element``.

    Section 8.2: The XML declaration is the first line; ElementTree handles it.
    Namespace prefixes (from xmlns:xsi etc.) are stripped from tag names so
    that callers can work with plain tag strings (e.g. ``"opm"``, ``"header"``).

    Uses ``defusedxml`` rather than stdlib ``ElementTree`` directly: CCSDS ODM/XML
    is a message-*exchange* format, so content legitimately arrives from external,
    only partially-trusted senders — raw ``ElementTree`` is vulnerable to
    entity-expansion ("billion laughs") DoS on such input.

    Raises:
        ParseError: If the XML document has no root element.
    """
    tree: ET.ElementTree = DefusedET.parse(path)
    if (root := tree.getroot()) is None:
        raise ParseError(f"{path}: XML document has no root element.")
    return root


def parse_xml_string(content: str) -> ET.Element:
    """
    Parse an ODM/XML string and return the root ``ET.Element``.

    Equivalent to ``parse_xml_file`` but operates on an in-memory string,
    enabling round-trip workflows without touching the filesystem. Uses
    ``defusedxml`` for the same reason as ``parse_xml_file``.

    Args:
        content (str): The XML content to parse.

    Returns:
        ET.Element: The root element of the parsed XML document.
    """
    return DefusedET.fromstring(content)


def strip_ns(tag: str) -> str:
    """
    Remove the Clark-notation namespace prefix {uri} from an XML tag.

    Section 8.3.3: The xsi namespace is required on the root element; child tags
    are not namespaced, but this function handles the defensive case.
    """
    return tag.split("}", 1)[-1] if "}" in tag else tag


def find_child(
    parent: ET.Element | None,
    tag: str,
) -> ET.Element | None:
    """
    Return the first direct child of ``parent`` whose bare tag equals ``tag``.

    Ignores any namespace prefix. Returns ``None`` if ``parent`` is ``None``,
    allowing safe chaining: ``find_child(find_child(root, "body"), "segment")``.

    Args:
        parent (ET.Element | None): The parent element to search, or ``None``.
        tag (str): The tag to search for.

    Returns:
        ET.Element | None: The first child element with the given tag, or ``None`` if not found.
    """
    if parent is None:
        return None
    for child in parent:
        if strip_ns(child.tag) == tag:
            return child
    return None


def find_all(
    parent: ET.Element | None,
    tag: str,
) -> list[ET.Element]:
    """
    Return all direct children of ``parent`` whose bare tag equals ``tag``.

    Returns an empty list if ``parent`` is ``None``.

    Args:
        parent (ET.Element | None): The parent element to search, or ``None``.
        tag (str): The tag to search for.

    Returns:
        list[ET.Element]: All child elements with the given tag. Order is preserved.
    """
    if parent is None:
        return []
    return [child for child in parent if strip_ns(child.tag) == tag]


def get_text(
    element: ET.Element | None,
    default: str = "",
) -> str:
    """
    Return ``element.text`` stripped of whitespace, or ``default``.

    ``default`` is returned when ``element`` is ``None`` or has no text.

    Args:
        element (ET.Element | None): The element to get the text from.
        default (str): The default text to return if the element is ``None`` or has no text.

    Returns:
        str: The text of the element, or the default text if the element is ``None`` or has no text.
    """
    if element is None:
        return default
    return (element.text or "").strip() or default
