"""
Wraps xml.etree.ElementTree and isolates all namespace handling in one place.
Returns Element objects: no domain types.  All namespace-stripping logic
lives here; adapters must not implement it themselves.

Spec references:
- Section 8.1: ODM keyword tags appear in all capitals; structural tags in lowerCamelCase.
- Section 8.2: First line: <?xml version="1.0" encoding="UTF-8"?>
- Section 8.3.3: xmlns:xsi namespace attribute on root element.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element


def parse_xml_file(path: Path) -> Element:
    """
    Parse an ODM/XML file and return the root Element.

    Section 8.2: The XML declaration is the first line; ElementTree handles it.
    Namespace prefixes (from xmlns:xsi etc.) are stripped from tag names so
    that callers can work with plain tag strings (e.g. 'opm', 'header').
    """
    tree: ET.ElementTree = ET.parse(path)
    return tree.getroot()


def strip_ns(tag: str) -> str:
    """
    Remove the Clark-notation namespace prefix {uri} from an XML tag.

    Section 8.3.3: The xsi namespace is required on the root element; child tags
    are not namespaced, but this function handles the defensive case.
    """
    return tag.split("}", 1)[-1] if "}" in tag else tag


def find_child(
    parent: Element,
    tag: str,
) -> Element | None:
    """
    Return the first direct child of ``parent`` whose bare tag equals ``tag``,
    ignoring any namespace prefix.

    Args:
        parent (Element): The parent element to search.
        tag (str): The tag to search for.

    Returns:
        Element | None: The first child element with the given tag, or ``None`` if not found.
    """
    for child in parent:
        if strip_ns(child.tag) == tag:
            return child
    return None


def find_all(
    parent: Element,
    tag: str,
) -> list[Element]:
    """
    Return all direct children of ``parent`` whose bare tag equals ``tag``.

    Args:
        parent (Element): The parent element to search.
        tag (str): The tag to search for.

    Returns:
        list[Element]: All child elements with the given tag. Order is preserved.
    """
    return [child for child in parent if strip_ns(child.tag) == tag]


def get_text(
    element: Element | None,
    default: str = "",
) -> str:
    """
    Return ``element.text`` stripped of leading/trailing whitespace, or ``default``
    when ``element`` is ``None`` or has no text.

    Args:
        element (Element | None): The element to get the text from.
        default (str): The default text to return if the element is ``None`` or has no text.

    Returns:
        str: The text of the element, or the default text if the element is ``None`` or has no text.
    """
    if element is None:
        return default
    return (element.text or "").strip() or default
