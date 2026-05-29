"""
Shared introspection helpers for XML adapters.

The same FieldMetadata(keyword=...) annotation that drives KVN keyword names
also drives XML element names: §8.1 states that ODM/XML tags for keywords
"appear just as in the KVN, that is, all capital letters."

read_model  — extract kwargs for a domain model class from an XML Element
write_model — write keyword child Elements under an XML parent Element
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from orbit_data_messages.io._utils import build_keyword_map
from orbit_data_messages.io._utils import format_value
from orbit_data_messages.io._utils import map_kvs
from orbit_data_messages.io.xml.parser import find_all
from orbit_data_messages.io.xml.parser import strip_ns
from orbit_data_messages.models.metadata import FieldMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel
    from xml.etree.ElementTree import Element
    from orbit_data_messages.io.options import WriterOptions


def read_model(
    element: Element,
    model_class: type[BaseModel],
    *,
    extra_kvs: dict[str, str] | None = None,
) -> dict:
    """
    Build Pydantic constructor kwargs for model_class by reading its direct
    child elements from element.

    §8.1 — ODM/XML keyword element names are all-caps, identical to KVN
    keywords; the same FieldMetadata(keyword=...) annotation is used here.
    §8.13.7 — COMMENT values are text content of <COMMENT> elements.
    §8.13.6 — units appear as element attributes; we ignore them on read
    (Pydantic validates the numerical value).

    extra_kvs, if provided, are merged in before building kwargs — used to
    inject the root-level version attribute into the header model.
    """
    kw_map = build_keyword_map(model_class)
    kvs: dict[str, str] = {}
    comments: list[str] = []

    for child in element:
        tag = strip_ns(child.tag)
        text = (child.text or "").strip()

        if tag == "COMMENT":
            comments.append(text)
        elif tag.startswith("USER_DEFINED_"):
            kvs[tag] = text
        elif tag in kw_map:
            kvs[tag] = text

    if extra_kvs:
        kvs.update(extra_kvs)

    return map_kvs(kvs, comments, model_class)


def write_model(
    model: BaseModel,
    parent: Element,
    *,
    skip_fields: frozenset[str] = frozenset(),
    options: "WriterOptions | None" = None,
) -> None:
    """
    Write keyword child elements for model under parent.

    §8.1 — Element tag names are the FieldMetadata keyword (all caps).
    §8.13.7 — Each COMMENT string becomes a separate <COMMENT> element.
    §8.13.6 / §8.10.18 — FieldMetadata.units is written as a units attribute
    when options.include_units is True (the default).

    skip_fields : Python field names to omit (e.g. 'ccsds_opm_vers', which
                  maps to the XML root version attribute, not a child element).
    options : formatting options; None uses WriterOptions() defaults.
    """
    kw_map_rev = {fn: kw for kw, fn in build_keyword_map(type(model)).items()}
    include_units = options is None or options.include_units

    for field_name in type(model).model_fields:
        if field_name in skip_fields:
            continue

        value = getattr(model, field_name)
        if value is None:
            continue

        kw = kw_map_rev.get(field_name)

        if kw == "COMMENT":
            # §8.13.7 — each comment line is its own <COMMENT> element.
            for c in value:
                el = ET.SubElement(parent, "COMMENT")
                el.text = c

        elif kw is not None:
            field_info = type(model).model_fields[field_name]
            # Resolve format spec: runtime override > model default.
            spec = next(
                (m.format_spec for m in field_info.metadata if isinstance(m, FieldMetadata)),
                None,
            )
            if options and options.float_formats and kw in options.float_formats:
                spec = options.float_formats[kw]

            el = ET.SubElement(parent, kw)
            # Strip sign-column leading space: in XML each value is in its own
            # element so the sign flag's extra space is cosmetic noise.
            el.text = format_value(value, spec).strip()

            # §8.13.6 — add units attribute when FieldMetadata carries units
            # and the caller has not opted out via options.include_units=False.
            if include_units:
                for meta in field_info.metadata:
                    if isinstance(meta, FieldMetadata) and meta.units:
                        el.set("units", meta.units)
                        break

        elif isinstance(value, dict):
            # USER_DEFINED_x pattern (§6.2.11.1 / §3.2.4.12 / §4.2.4.10).
            for k, v in value.items():
                el = ET.SubElement(parent, f"USER_DEFINED_{k}")
                el.text = str(v)
