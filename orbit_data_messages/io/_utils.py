"""
Format-agnostic helpers for mapping between ``FieldMetadata`` annotations on domain models
and the keyword / element names that appear in serialized files. Both KVN and XML adapters
use these helpers.

build_keyword_map : ``{KVN_keyword: pydantic_field_name}`` for a model class
map_kvs           : build ``pydantic.BaseModel`` constructor kwargs from parsed key-value pairs
format_value      : convert a Python field value to its serialized string form (section 7.5.4, 7.5.5)
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from typing import Any

from orbit_data_messages.models.metadata import FieldMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel


def build_keyword_map(model_class: type[BaseModel]) -> dict[str, str]:
    """
    Return ``{KVN_keyword: pydantic_field_name}`` for every ``FieldMetadata`` (keyword=...) -annotated field.

    Only direct fields of ``model_class`` are considered; nested classes are
    not traversed: callers pass the specific class they need.

    Args:
        model_class (type[BaseModel]): ``pydantic.BaseModel`` class whose fields carry
            ``FieldMetadata(keyword=...)`` annotations.

    Returns:
        dict[str, str]: Mapping from CCSDS keyword string to ``pydantic.BaseModel`` field name.
    """
    result: dict[str, str] = {}
    for field_name, field_info in model_class.model_fields.items():
        for item in field_info.metadata:
            if isinstance(item, FieldMetadata):
                result[item.keyword] = field_name
    return result


def map_kvs(
    kvs: dict[str, str],
    comments: list[str],
    model_class: type[BaseModel],
) -> dict[str, Any]:
    """
    Build ``pydantic.BaseModel`` constructor kwargs from parsed key-value pairs and comments.

    Keyword-to-field mapping comes from ``FieldMetadata`` (keyword=...) annotations; nothing is
    hardcoded. ``pydantic.BaseModel`` lax-mode coercion converts strings to numeric and enum
    types. ``COMMENT`` lines are injected via the model's ``comment`` field when
    present. ``USER_DEFINED_x`` keys are gathered into a ``user_defined`` dict
    keyed by the suffix ``x``. Unknown keywords are silently ignored for forward
    compatibility.

    Args:
        kvs (dict[str, str]): Parsed ``{keyword: value}`` pairs from the file.
        comments (list[str]): Accumulated comment texts to attribute to this block.
        model_class (type[BaseModel]): Target ``pydantic.BaseModel`` class whose fields receive
            the mapped values.

    Returns:
        dict[str, Any]: Constructor kwargs ready for ``model_class(**kwargs)``.
    """
    keyword_map: dict[str, str] = build_keyword_map(model_class)
    kwargs: dict[str, Any] = {}

    for keyword, value in kvs.items():
        # USER_DEFINED_x: aggregate into a dict.
        if keyword.startswith('USER_DEFINED_'):
            suffix: str = keyword[len('USER_DEFINED_'):]
            kwargs.setdefault('user_defined', {})[suffix] = value
            continue

        field_name: str | None = keyword_map.get(keyword)
        if field_name is None:
            continue  # Unknown keyword: forward-compatible skip.

        kwargs[field_name] = value

    # Inject comments when the model has a ``comment`` field.
    comment_field: str | None = keyword_map.get('COMMENT')
    if comment_field and comments:
        kwargs[comment_field] = comments

    return kwargs


def format_value(
    value: object,
    spec: str | None = None,
) -> str:
    """
    Serialize a Python field value to its CCSDS string representation.

    Integers are formatted as decimal digits (section 7.5.4). Non-integer numerics
    use fixed-point or floating-point notation (section 7.5.5). ``StrEnum`` members
    emit their ``.value``: the spec-defined string. All other values are
    converted with ``str()``.

    Args:
        value (object): The field value to serialize.
        spec (str | None): Python format-spec string from ``FieldMetadata.format_spec``.
            When provided, floats are formatted with ``format(value, spec)`` instead
            of ``repr()``. Defaults to None.

    Returns:
        str: The serialized string suitable for writing to a KVN or XML file.
    """
    if isinstance(value, Enum):
        return value.value  # StrEnum.value is the spec-defined string
    if isinstance(value, float):
        return format(value, spec) if spec is not None else repr(value)
    return str(value)
