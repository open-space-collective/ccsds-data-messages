"""
Format-agnostic helpers shared by the KVN and XML adapters.

Maps between ``FieldMetadata`` annotations on domain models and the keyword /
element names that appear in serialized files.

build_keyword_map  : ``{KVN_keyword: pydantic_field_name}`` for a model class
map_kvs            : build ``pydantic.BaseModel`` constructor kwargs from parsed key-value pairs
format_value       : convert a Python field value to its serialized string form (section 7.5.4, 7.5.5)
format_ccsds_epoch : format a ``datetime`` to a CCSDS calendar epoch string (section 7.5.10)
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

from ccsds_data_messages.models._fields import FieldMetadata

if TYPE_CHECKING:
    from datetime import datetime

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
        if keyword.startswith("USER_DEFINED_"):
            suffix: str = keyword[len("USER_DEFINED_") :]
            kwargs.setdefault("user_defined", {})[suffix] = value
            continue

        if (field_name := keyword_map.get(keyword)) is None:
            continue  # Unknown keyword: forward-compatible skip.

        kwargs[field_name] = value

    # Inject comments when the model has a ``comment`` field.
    comment_field: str | None = keyword_map.get("COMMENT")
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
        return str(value.value)  # StrEnum.value is the spec-defined string
    if isinstance(value, float):
        if not math.isfinite(value):
            # §7.5.6/7.5.7 define fixed-point and floating-point values as closed
            # grammars ("shall consist of" decimal digits, sign, exponent digits) -
            # neither grammar can produce "nan"/"inf"/"-inf", so they have no valid
            # serialization, even though the spec never names NaN/Inf explicitly.
            raise ValueError(
                f"KVN/XML numeric fields must be finite; got {value!r}. "
                "Reject NaN/±Inf before writing (no representation under §7.5.6/7.5.7)."
            )
        # Section 7.5.6-7.5.7: max 16 significant digits. ".15g" gives at most 15,
        # using the shorter of fixed-point or scientific notation.
        return format(value, spec) if spec is not None else format(value, ".15g")
    return str(value)


def format_ccsds_epoch(dt: datetime, *, include_z: bool = True) -> str:
    """
    Format a stdlib ``datetime`` to a CCSDS calendar epoch string.

    Always produces the calendar format (``YYYY-MM-DDThh:mm:ss[.d+]``).
    Sub-second precision is included only when non-zero; trailing zeros are stripped.

    Args:
        dt (datetime): A ``datetime`` (timezone-aware or naive). Timezone info is
            not included in the output; callers are responsible for ensuring ``dt``
            is in the correct time scale for the field being serialized.
        include_z (bool): Whether to append the UTC ``Z`` suffix. Defaults to
            ``True`` per CCSDS §7.5.10 producer guidance. Pass ``False`` only
            when the downstream consumer is known to not accept the suffix.

    Returns:
        str: A CCSDS calendar epoch string, e.g. ``"2025-01-15T12:30:45.5Z"``.
    """
    result: str = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        result += f".{dt.microsecond:06d}".rstrip("0")
    if include_z:
        result += "Z"
    return result


def _normalize_fmt(fmt: str) -> str:
    return fmt.strip().lower()


def _normalize_type(message_type: str) -> str:
    return message_type.strip().lower()
