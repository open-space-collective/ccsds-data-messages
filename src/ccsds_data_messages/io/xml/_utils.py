"""
Shared introspection helpers for XML adapters.

The same ``FieldMetadata(keyword=...)`` annotation that drives KVN keyword names
also drives XML element names: Section 8.1 states that ODM/XML tags for keywords
'appear just as in the KVN, that is, all capital letters.' Tags related to the
message structure are in lowerCamelCase.
"""

from __future__ import annotations

# Build/serialize only in this module - parsing untrusted XML goes through
# io.xml.parser, which uses defusedxml.
import re
import xml.etree.ElementTree as ET  # noqa: S405
from typing import TYPE_CHECKING
from typing import Any

from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io._utils import build_keyword_map
from ccsds_data_messages.io._utils import format_value
from ccsds_data_messages.io._utils import map_kvs
from ccsds_data_messages.io.xml.parser import strip_ns
from ccsds_data_messages.models._fields import FieldMetadata

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel
    from pydantic.fields import FieldInfo

    from ccsds_data_messages.io.options import WriterOptions

# Structural XML element names with no corresponding model class (section 8.5-8.7).
# Model classes that DO have an XML tag declare it via ``_xml_tag: ClassVar[str]``;
# adapters call ``get_xml_tag(cls)`` to read it, mirroring ``get_delineation()`` in KVN.
_TAG_BODY: str = "body"  # Pure XML structural envelope; no domain model.
_TAG_SEGMENT: str = (
    "segment"  # OPM/OMM/OCM have no Segment model (OEM.Segment uses get_xml_tag).
)
_TAG_DATA: str = "data"  # OCM and OEM have no Data model wrapping the section.

# NDM/XML root-element attributes, identical across all four message writers.
_XMLNS_XSI: str = "http://www.w3.org/2001/XMLSchema-instance"
_NDM_SCHEMA: str = (
    "https://sanaregistry.org/r/ndmxml_unqualified/ndmxml-3.0.0-master-3.0.xsd"
)

# The version keyword of every ODM message matches CCSDS_<TYPE>_VERS (section 7.4.2).
# It is the header's ``id`` attribute in NDM/XML and doubles as the ``version`` value.
_VERSION_KEYWORD_RE = re.compile(r"^CCSDS_[A-Z]+_VERS$")


def build_ndm_root(message_class: type, header: BaseModel) -> ET.Element:
    """
    Build the root NDM/XML element for a message, with its standard attributes.

    Every ODM/XML message shares the same root envelope (section 8.4): the
    ``xmlns:xsi`` and ``xsi:noNamespaceSchemaLocation`` namespace attributes, an
    ``id`` naming the version keyword (e.g. ``CCSDS_OPM_VERS``), and the ``version``
    string. Both the ``id`` and the version value are derived from the header's
    ``FieldMetadata`` - like every other keyword, nothing is hardcoded here.

    Args:
        message_class (type): The message model class, whose ``_xml_tag`` names the
            root element (e.g. ``OPM`` -> ``<opm>``).
        header (BaseModel): The message header instance, carrying the version field.

    Returns:
        ET.Element: The configured root element, ready for header/body sub-elements.

    Raises:
        ValueError: If the header declares no ``CCSDS_<TYPE>_VERS`` keyword.
    """
    version_keyword, version_field = _version_keyword_field(type(header))
    root: ET.Element = ET.Element(get_xml_tag(message_class))
    root.set("xmlns:xsi", _XMLNS_XSI)
    root.set("xsi:noNamespaceSchemaLocation", _NDM_SCHEMA)
    root.set("id", version_keyword)
    root.set("version", str(getattr(header, version_field)))
    return root


def _version_keyword_field(header_class: type[BaseModel]) -> tuple[str, str]:
    """Return the ``(keyword, field_name)`` of a header's ``CCSDS_<TYPE>_VERS`` field."""
    for keyword, field_name in build_keyword_map(header_class).items():
        if _VERSION_KEYWORD_RE.match(keyword):
            return keyword, field_name
    raise ValueError(
        f"{header_class.__qualname__} declares no CCSDS_<TYPE>_VERS version keyword."
    )


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
        TypeError: If ``_xml_tag`` is present but not a ``str``.
    """
    if (tag := getattr(model_class, "_xml_tag", None)) is None:
        raise AttributeError(
            f"{model_class.__qualname__} has no '_xml_tag' class variable. "
            "Add '_xml_tag: ClassVar[str] = \"...\"' to the class body."
        )
    if not isinstance(tag, str):
        raise TypeError(
            f"{model_class.__qualname__}'s '_xml_tag' class variable must be a str, "
            f"got {type(tag).__name__}."
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
        TypeError: If ``_xml_line_tag`` is present but not a ``str``.
    """
    if (tag := getattr(model_class, "_xml_line_tag", None)) is None:
        raise AttributeError(
            f"{model_class.__qualname__} has no '_xml_line_tag' class variable. "
            "Add '_xml_line_tag: ClassVar[str] = \"...\"' to the class body."
        )
    if not isinstance(tag, str):
        raise TypeError(
            f"{model_class.__qualname__}'s '_xml_line_tag' class variable must be a "
            f"str, got {type(tag).__name__}."
        )
    return tag


def read_model(
    element: ET.Element | None,
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
        element (ET.Element | None): The XML ``Element`` whose direct children carry
            keyword values. Readers commonly pass the result of ``find_child()``, which
            is ``None`` when the expected child element is missing.
        model_class (type[BaseModel]): The target Pydantic model class.
        extra_kvs (dict[str, str] | None): Additional key-value pairs merged in
            before building kwargs: used to inject the root-level ``version``
            attribute into the header model. Defaults to None.

    Returns:
        dict[str, Any]: Constructor kwargs ready for ``model_class(**kwargs)``.

    Raises:
        ParseError: If ``element`` is ``None`` (the expected element was missing).
    """
    if element is None:
        raise ParseError(
            f"Expected an XML element for {model_class.__qualname__}, found none."
        )

    keyword_map: dict[str, str] = build_keyword_map(model_class)
    kvs: dict[str, str] = {}
    comments: list[str] = []

    for child in element:
        tag: str = strip_ns(child.tag)
        text: str = (child.text or "").strip()

        if tag == "COMMENT":
            comments.append(text)
        elif tag == "USER_DEFINED":
            # Spec form: the key lives in the ``parameter`` attribute,
            # e.g. <USER_DEFINED parameter="EARTH_MODEL">WGS-84</USER_DEFINED>.
            # Normalize to the USER_DEFINED_x key shape that map_kvs aggregates.
            if (param := child.get("parameter")) is not None:
                kvs[f"USER_DEFINED_{param}"] = text
        elif tag.startswith("USER_DEFINED_") or tag in keyword_map:
            # Back-compat: tolerate the legacy <USER_DEFINED_x> element form.
            kvs[tag] = text

    if extra_kvs:
        kvs.update(extra_kvs)

    return map_kvs(kvs, comments, model_class)


def write_model(
    model: BaseModel,
    parent: ET.Element,
    *,
    skip_fields: frozenset[str] = frozenset(),
    options: WriterOptions | None = None,
) -> None:
    """
    Write keyword child elements for ``model`` under ``parent`` (section 8.1).

    Element tag names are the ``FieldMetadata`` keyword (all-caps). Each
    ``COMMENT`` string becomes a separate ``<COMMENT>`` element (section 8.13.7).
    When ``options.include_units`` is ``True`` (the default), a ``units``
    attribute is added when ``FieldMetadata`` carries units (section 8.13.6/section 8.10.18).
    ``USER_DEFINED_x`` fields become ``<USER_DEFINED parameter="x">`` elements
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
    keyword_map_rev: dict[str, str] = {
        field_name: keyword
        for keyword, field_name in build_keyword_map(type(model)).items()
    }
    include_units: bool = options is None or options.include_units
    suppress: bool = options is not None and bool(options.suppress_defaults)

    for field_name in type(model).model_fields:
        if field_name in skip_fields:
            continue

        if (value := getattr(model, field_name)) is None:
            continue
        if suppress:
            # (a) A field with a non-None Python default (e.g. OCM's
            # TIME_SYSTEM = UTC) that the source omitted: not in model_fields_set.
            if field_name not in model.model_fields_set:
                continue
            # (b) A field explicitly set to its CCSDS spec-defined default.
            field_info_for_suppress: FieldInfo = type(model).model_fields[field_name]
            spec_default = next(
                (
                    m.spec_default
                    for m in field_info_for_suppress.metadata
                    if isinstance(m, FieldMetadata)
                ),
                None,
            )
            if spec_default is not None and value == spec_default:
                continue

        keyword: str | None = keyword_map_rev.get(field_name)

        if keyword == "COMMENT":
            # Section 8.13.7: each comment line is its own <COMMENT> element.
            for comment_text in value:
                comment_element: ET.Element = ET.SubElement(parent, "COMMENT")
                comment_element.text = comment_text

        elif keyword is not None:
            field_info: FieldInfo = type(model).model_fields[field_name]
            # Resolve format spec: runtime override > model default.
            spec: str | None = next(
                (
                    m.format_spec
                    for m in field_info.metadata
                    if isinstance(m, FieldMetadata)
                ),
                None,
            )
            if options and options.float_formats and keyword in options.float_formats:
                spec = options.float_formats[keyword]

            keyword_element: ET.Element = ET.SubElement(parent, keyword)
            # Strip sign-column leading space: in XML each value is in its own
            # element so the sign flag's extra space is cosmetic noise.
            keyword_element.text = format_value(value, spec).strip()

            # Section 8.13.6: add units attribute when FieldMetadata carries units
            # and the caller has not opted out via options.include_units=False.
            if include_units:
                for metadata in field_info.metadata:
                    if isinstance(metadata, FieldMetadata) and metadata.units:
                        keyword_element.set("units", metadata.units)
                        break

        elif isinstance(value, dict):
            # User-defined parameters (section 6.2.11.1 / section 3.2.4.12 / section 4.2.4.10).
            # ODM/XML carries the key in a ``parameter`` attribute on a bare
            # <USER_DEFINED> element, e.g.
            # <USER_DEFINED parameter="EARTH_MODEL">WGS-84</USER_DEFINED>.
            for user_key, user_value in value.items():
                user_defined_element: ET.Element = ET.SubElement(parent, "USER_DEFINED")
                user_defined_element.set("parameter", user_key)
                user_defined_element.text = str(user_value)


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
