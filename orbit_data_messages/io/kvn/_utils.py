"""
Shared introspection helpers for KVN adapters (readers and writers).

Adapters use these to map between KVN keyword strings and Pydantic field names
without hardcoding keyword strings.  The keyword strings live on the domain
model as FieldMetadata(keyword=...) annotations; these helpers read them at
runtime.

Writer utilities
----------------
format_value  — convert a Python field value to its KVN string
emit_kvs      — write all non-None KV pairs for a model in field order
emit_block    — write a model block, optionally wrapped in *_START/*_STOP
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from typing import TextIO

from orbit_data_messages.models.metadata import Delineation
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


def get_delineation(model_class: type[BaseModel]) -> Delineation | None:
    """
    Read the Delineation private attribute from model_class, if present.

    Returns the Delineation instance (with .start and .stop), or None when
    the class does not carry block-delimiter metadata.
    """
    priv = model_class.__private_attributes__.get('_delineation')
    if priv is not None and priv.default_factory is not None:
        return priv.default_factory()
    return None


def block_delimiter_name(model_class: type[BaseModel]) -> str | None:
    """
    Return the block type string (e.g. 'META', 'COVARIANCE') used as the
    'delimiter' key in split_blocks output, derived from the model's
    Delineation.start (e.g. 'META_START' → 'META').

    Returns None when the class has no Delineation.
    """
    d = get_delineation(model_class)
    if d is None:
        return None
    return d.start.removesuffix('_START')


def field_keyword(model_class: type[BaseModel], field_name: str) -> str:
    """
    Return the KVN keyword string for a specific field, identified by its
    Python attribute name.

    This is the only sanctioned way for an adapter to obtain the keyword for
    a field it needs to treat specially (e.g. as a block-separator key).  The
    keyword string is read from the model's FieldMetadata annotation; no
    keyword string is hardcoded in the adapter.

    Raises ValueError if the field has no FieldMetadata(keyword=...).
    """
    for field_info_name, field_info in model_class.model_fields.items():
        if field_info_name != field_name:
            continue
        for item in field_info.metadata:
            if isinstance(item, FieldMetadata):
                return item.keyword
    raise ValueError(
        f"{model_class.__qualname__}.{field_name} has no FieldMetadata(keyword=...). "
        f"Every field used as a structural key must carry a keyword annotation."
    )


def map_kvs(
    kvs: dict[str, str],
    comments: list[str],
    model_class: type[BaseModel],
) -> dict:
    """
    Build Pydantic constructor kwargs for model_class from KVN key-value
    pairs and accumulated comment texts.

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


# ---------------------------------------------------------------------------
# Writer utilities
# ---------------------------------------------------------------------------

def format_value(value: object) -> str:
    """
    Format a Python field value as a KVN-compliant string.

    Rules (§7.5)
    ------------
    §7.5.4  Integers: decimal digits with optional leading sign.
    §7.5.5  Non-integer numerics: fixed-point or floating-point.
    §7.5.2  Free-text and comment values: any case.
    Enum values (StrEnum): use .value — the string the spec defines.
    """
    if isinstance(value, Enum):
        return value.value  # StrEnum.value is the spec-defined string
    if isinstance(value, float):
        return repr(value)  # shortest round-trip representation (§7.5.5–7.5.7)
    return str(value)


def emit_kvs(model: BaseModel, out: TextIO) -> None:
    """
    Write KV pairs for all non-None fields of model in declaration order.

    Field iteration uses model_fields (preserves spec-mandated order per
    §7.4.8).  Each field is written using the keyword from its FieldMetadata
    annotation — no keyword strings are hardcoded here.

    Special cases
    -------------
    - COMMENT fields (list[str]): written as 'COMMENT text' lines (§7.8.5).
    - dict fields with no FieldMetadata: written as 'USER_DEFINED_k = v'
      pairs (§3.2.4.12, §4.2.4.10, §6.2.11.1).
    - Fields with no FieldMetadata and not a dict (e.g., data_lines in OCM
      blocks): silently skipped — caller handles them separately.
    """
    kw_map = build_keyword_map(type(model))
    field_to_kw = {fn: kw for kw, fn in kw_map.items()}

    for field_name in type(model).model_fields:
        value = getattr(model, field_name)
        if value is None:
            continue

        kw = field_to_kw.get(field_name)

        if kw == 'COMMENT':
            # §7.8.5 — every comment line begins with the COMMENT keyword.
            for line_text in value:
                out.write(f"COMMENT {line_text}\n")
        elif kw is not None:
            out.write(f"{kw} = {format_value(value)}\n")
        elif isinstance(value, dict):
            # USER_DEFINED_x pattern — spec §3.2.4.12, §4.2.4.10, §6.2.11.1.
            for k, v in value.items():
                out.write(f"USER_DEFINED_{k} = {v}\n")
        # else: field has no FieldMetadata and is not a dict → skip.


def emit_block(
    model: BaseModel,
    out: TextIO,
    *,
    extra_lines: list[str] | None = None,
) -> None:
    """
    Write a complete named block for model.

    If model carries a _delineation PrivateAttr (OEM.Segment.Metadata,
    OCM.TrajectoryStateBlock, …), the block is wrapped in its START/STOP
    keywords.  For flat models without Delineation (OPM.Metadata, etc.)
    the KVs are written with no delimiters.

    extra_lines, if provided, are written verbatim after the KV pairs but
    before the STOP keyword.  Used for OCM/OEM raw data rows (trajectory
    states, maneuver lines, covariance rows) that are stored as list[str]
    without FieldMetadata.
    """
    d = get_delineation(type(model))
    if d:
        out.write(f"{d.start}\n")
    emit_kvs(model, out)
    if extra_lines:
        for line in extra_lines:
            out.write(f"{line}\n")
    if d:
        out.write(f"{d.stop}\n")
