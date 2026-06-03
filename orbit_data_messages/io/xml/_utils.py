"""
Shared introspection helpers for XML adapters.

The same ``FieldMetadata(keyword=...)`` annotation that drives KVN keyword names
also drives XML element names: section 8.1 states that ODM/XML tags for keywords
'appear just as in the KVN, that is, all capital letters.' Tags related to the
message structure are in lowerCamelCase.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from pydantic.fields import FieldInfo

from orbit_data_messages.io._utils import build_keyword_map
from orbit_data_messages.io._utils import format_value
from orbit_data_messages.io._utils import map_kvs
from orbit_data_messages.io.xml.parser import strip_ns
from orbit_data_messages.models.metadata import FieldMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel
    from orbit_data_messages.io.options import WriterOptions

# Structural XML element names with no corresponding model class (section 8.5–8.7).
# Model classes that DO have an XML tag declare it via ``_xml_tag: ClassVar[str]``;
# adapters call ``get_xml_tag(cls)`` to read it, mirroring ``get_delineation()`` in KVN.
_TAG_BODY: str = "body"       # Pure XML structural envelope; no domain model.
_TAG_SEGMENT: str = "segment" # OPM/OMM/OCM have no Segment model (OEM.Segment uses get_xml_tag).
_TAG_DATA: str = "data"       # OCM and OEM have no Data model wrapping the section.


def get_xml_tag(model_class: type) -> str:
    """
    Return the XML structural element tag declared on ``model_class`` via ``_xml_tag``.

    Analogous to ``get_delineation()`` in the KVN adapter: model classes carry
    ``_xml_tag: ClassVar[str]`` so adapters derive the element name from the model
    rather than hardcoding it.

    Args:
        model_class (type): The model class to inspect.

    Returns:
        str: The ``_xml_tag`` value.

    Raises:
        AttributeError: If the class has no ``_xml_tag`` class variable.
    """
    tag: str | None = getattr(model_class, "_xml_tag", None)
    if not isinstance(tag, str):
        raise AttributeError(
            f"{model_class.__qualname__} has no '_xml_tag' class variable. "
            "Add '_xml_tag: ClassVar[str] = \"...\"' to the class body."
        )
    return tag


def get_xml_line_tag(model_class: type) -> str:
    """
    Return the XML data-line element tag declared on ``model_class`` via ``_xml_line_tag``.

    Analogous to ``get_xml_tag()``, but for the sub-element that holds individual
    raw data lines within an OCM block (e.g. ``<trajLine>``, ``<covLine>``,
    ``<manLine>`` per section 8.11.15).

    Args:
        model_class (type): The model class to inspect.

    Returns:
        str: The ``_xml_line_tag`` value.

    Raises:
        AttributeError: If the class has no ``_xml_line_tag`` class variable.
    """
    tag: str | None = getattr(model_class, "_xml_line_tag", None)
    if not isinstance(tag, str):
        raise AttributeError(
            f"{model_class.__qualname__} has no '_xml_line_tag' class variable. "
            "Add '_xml_line_tag: ClassVar[str] = \"...\"' to the class body."
        )
    return tag


def read_model(
    element: ET.Element,
    model_class: type[BaseModel],
    *,
    extra_kvs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build Pydantic constructor kwargs by reading direct child elements (section 8.1).

    ODM/XML keyword element names are all-caps and identical to KVN keywords;
    the same ``FieldMetadata(keyword=...)`` annotation drives both formats.
    ``COMMENT`` element text is collected as a list (section 8.13.7). Units attributes
    on elements are ignored on read: Pydantic validates numerical values (section 8.13.6).

    Args:
        element (ET.Element): The XML ``Element`` whose direct children carry keyword values.
        model_class (type[BaseModel]): The target Pydantic model class.
        extra_kvs (dict[str, str] | None): Additional key-value pairs merged in
            before building kwargs: used to inject the root-level ``version``
            attribute into the header model. Defaults to None.

    Returns:
        dict[str, Any]: Constructor kwargs ready for ``model_class(**kwargs)``.
    """
    keyword_map: dict[str, str] = build_keyword_map(model_class)
    kvs: dict[str, str] = {}
    comments: list[str] = []

    for child in element:
        tag: str = strip_ns(child.tag)
        text: str = (child.text or "").strip()

        if tag == "COMMENT":
            comments.append(text)
        elif tag.startswith("USER_DEFINED_"):
            kvs[tag] = text
        elif tag in keyword_map:
            kvs[tag] = text

    if extra_kvs:
        kvs.update(extra_kvs)

    return map_kvs(kvs, comments, model_class)


def write_model(
    model: BaseModel,
    parent: ET.Element,
    *,
    skip_fields: frozenset[str] = frozenset(),
    options: "WriterOptions | None" = None,
) -> None:
    """
    Write keyword child elements for ``model`` under ``parent`` (section 8.1).

    Element tag names are the ``FieldMetadata`` keyword (all-caps). Each
    ``COMMENT`` string becomes a separate ``<COMMENT>`` element (section 8.13.7).
    When ``options.include_units`` is ``True`` (the default), a ``units``
    attribute is added when ``FieldMetadata`` carries units (section 8.13.6/section 8.10.18).
    ``USER_DEFINED_x`` fields become ``<USER_DEFINED_x>`` elements
    (section 6.2.11.1/section 3.2.4.12/section 4.2.4.10).

    Args:
        model (BaseModel): The Pydantic model instance to serialize.
        parent (ET.Element): The XML ``Element`` under which keyword child elements are
            appended.
        skip_fields (frozenset[str]): The Python field names to omit, e.g.
            ``'ccsds_opm_vers'`` which maps to the XML root ``version``
            attribute rather than a child element. Defaults to empty frozenset.
        options (WriterOptions | None): The formatting options. Defaults to None,
            which applies ``WriterOptions()`` defaults.
    """
    keyword_map_rev: dict[str, str] = {field_name: keyword for keyword, field_name in build_keyword_map(type(model)).items()}
    include_units: bool = options is None or options.include_units

    for field_name in type(model).model_fields:
        if field_name in skip_fields:
            continue

        value: Any = getattr(model, field_name)
        if value is None:
            continue

        keyword: str | None = keyword_map_rev.get(field_name)

        if keyword == "COMMENT":
            # Section 8.13.7: each comment line is its own <COMMENT> element.
            for comment_text in value:
                element: ET.Element = ET.SubElement(parent, "COMMENT")
                element.text: str = comment_text

        elif keyword is not None:
            field_info: FieldInfo = type(model).model_fields[field_name]
            # Resolve format spec: runtime override > model default.
            spec: str | None = next(
                (m.format_spec for m in field_info.metadata if isinstance(m, FieldMetadata)),
                None,
            )
            if options and options.float_formats and keyword in options.float_formats:
                spec = options.float_formats[keyword]

            element: ET.Element = ET.SubElement(parent, keyword)
            # Strip sign-column leading space: in XML each value is in its own
            # element so the sign flag's extra space is cosmetic noise.
            element.text: str = format_value(value, spec).strip()

            # Section 8.13.6: add units attribute when FieldMetadata carries units
            # and the caller has not opted out via options.include_units=False.
            if include_units:
                for metadata in field_info.metadata:
                    if isinstance(metadata, FieldMetadata) and metadata.units:
                        element.set("units", metadata.units)
                        break

        elif isinstance(value, dict):
            # USER_DEFINED_x pattern (section 6.2.11.1 / section 3.2.4.12 / section 4.2.4.10).
            for key, value in value.items():
                element: ET.Element = ET.SubElement(parent, f"USER_DEFINED_{key}")
                element.text: str = str(value)


def serialize_xml(root: ET.Element) -> str:
    """
    Serialize an XML element tree to a UTF-8 string with an XML 1.0 declaration.

    Equivalent to ``write_xml_file`` but returns the content as a string instead
    of writing to disk, enabling in-memory round-trip workflows.

    Args:
        root (ET.Element): The root element of the document to serialize.

    Returns:
        str: The serialized XML content, including the XML declaration.
    """
    ET.indent(root, space="  ")
    xml_body: str = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body


def write_xml_file(
    root: ET.Element,
    path: Path,
) -> None:
    """
    Serialize an XML element tree to a UTF-8 file with an XML 1.0 declaration.

    Args:
        root (ET.Element): The root element of the document to serialize.
        path (Path): The destination file path; created or overwritten.
    """
    path.write_text(serialize_xml(root), encoding="utf-8")
