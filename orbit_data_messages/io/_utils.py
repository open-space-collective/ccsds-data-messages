"""
Shared model-introspection and value-formatting utilities for I/O adapters.

These helpers are format-agnostic: both KVN and XML adapters use them to
map between FieldMetadata annotations on domain models and the keyword /
element names that appear in serialized files.

build_keyword_map  — {KVN_keyword: pydantic_field_name} for a model class
map_kvs            — build Pydantic constructor kwargs from parsed key-value pairs
format_value       — convert a Python field value to its serialized string form
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from orbit_data_messages.models.metadata import FieldMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel


def build_keyword_map(model_class: type[BaseModel]) -> dict[str, str]:
    """
    Return {KVN_keyword: pydantic_field_name} by reading FieldMetadata
    annotations on every field of model_class.

    Only direct fields of model_class are considered; nested classes are
    not traversed — callers pass the specific class they need.
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
) -> dict:
    """
    Build Pydantic constructor kwargs for model_class from key-value pairs
    and accumulated comment texts.

    Rules
    -----
    - Keyword → field name mapping is read from FieldMetadata annotations;
      no keyword string is hardcoded here.
    - Pydantic v2 lax-mode coercion handles str→float/int/enum conversion.
    - COMMENT lines are injected as list[str] via the 'comment' field when
      the model carries one.
    - USER_DEFINED_x keywords are gathered into a 'user_defined' dict using
      the suffix x as the key.
    - Unknown keywords (not in any FieldMetadata) are silently ignored so
      that forward-compatible messages do not raise.
    """
    keyword_map = build_keyword_map(model_class)
    kwargs: dict = {}

    for keyword, value in kvs.items():
        # USER_DEFINED_x — aggregate into a dict.
        if keyword.startswith('USER_DEFINED_'):
            suffix = keyword[len('USER_DEFINED_'):]
            kwargs.setdefault('user_defined', {})[suffix] = value
            continue

        field_name = keyword_map.get(keyword)
        if field_name is None:
            continue  # unknown keyword — forward-compatible skip

        kwargs[field_name] = value

    # Inject comments when the model has a 'comment' field.
    comment_field = keyword_map.get('COMMENT')
    if comment_field and comments:
        kwargs[comment_field] = comments

    return kwargs


def format_value(value: object, spec: str | None = None) -> str:
    """
    Format a Python field value as a serialized string.

    Rules (§7.5)
    ------------
    §7.5.4  Integers: decimal digits with optional leading sign.
    §7.5.5  Non-integer numerics: fixed-point or floating-point.
    §7.5.2  Free-text and comment values: any case.
    Enum values (StrEnum): use .value — the string the spec defines.

    spec: Python format-spec string (from FieldMetadata.format_spec).  When
    provided, floats are formatted with format(value, spec) instead of repr().
    """
    if isinstance(value, Enum):
        return value.value  # StrEnum.value is the spec-defined string
    if isinstance(value, float):
        return format(value, spec) if spec is not None else repr(value)
    return str(value)
