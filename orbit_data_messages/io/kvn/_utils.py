"""
KVN-specific introspection and serialization helpers.

Generic model-introspection utilities (build_keyword_map, map_kvs,
format_value) live in io._utils and are re-exported here for convenience.

KVN-only helpers
----------------
get_delineation    — read the Delineation ClassVar from a model class
block_delimiter_name — derive the block type string from a Delineation
field_keyword      — look up the keyword string for a named field
emit_kvs           — write all non-None KV pairs for a model in field order
emit_block         — write a model block, optionally wrapped in *_START/*_STOP
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TextIO

from orbit_data_messages.io._utils import build_keyword_map
from orbit_data_messages.io._utils import format_value
from orbit_data_messages.io._utils import map_kvs
from orbit_data_messages.models.metadata import Delineation
from orbit_data_messages.models.metadata import FieldMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel
    from orbit_data_messages.io.options import WriterOptions

# Re-export so existing callers that import from this module continue to work.
__all__ = [
    "build_keyword_map",
    "format_value",
    "map_kvs",
    "get_delineation",
    "block_delimiter_name",
    "field_keyword",
    "emit_kvs",
    "emit_block",
]


def get_delineation(model_class: type[BaseModel]) -> Delineation | None:
    """
    Return the Delineation ClassVar from model_class, if present.

    Nested block model classes (e.g. OEM.Segment.Metadata) carry a
    `_delineation: ClassVar[Delineation]` that names the START/STOP keywords
    for that block.  Returns None when the class carries no such annotation.
    """
    attr = getattr(model_class, '_delineation', None)
    return attr if isinstance(attr, Delineation) else None


def block_delimiter_name(model_class: type[BaseModel]) -> str | None:
    """
    Return the block type string (e.g. 'META', 'COVARIANCE') used as the
    'delimiter' key in split_blocks output, derived from the model's
    Delineation.start (e.g. 'META_START' → 'META').

    Returns None when the class has no Delineation.
    """
    delineation = get_delineation(model_class)
    if delineation is None:
        return None
    return delineation.start.removesuffix('_START')


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


def emit_kvs(model: BaseModel, out: TextIO, *, options: "WriterOptions | None" = None) -> None:
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

    When options.align_keywords is True (default), keywords within the block
    are right-padded so the '=' signs align in a column (§7.4.5 — whitespace
    around keywords is insignificant).
    """
    kw_map = build_keyword_map(type(model))
    field_to_kw = {fn: kw for kw, fn in kw_map.items()}
    align = options is not None and options.align_keywords

    # Phase 1 — collect entries.
    # Each entry is one of:
    #   ("_comment", text, None)          — COMMENT line
    #   ("_user", "USER_DEFINED_k", value) — USER_DEFINED pair
    #   (keyword, value, spec)             — normal KV pair
    entries: list[tuple[str, object, object]] = []

    for field_name, field_info in type(model).model_fields.items():
        value = getattr(model, field_name)
        if value is None:
            continue

        kw = field_to_kw.get(field_name)

        if kw == 'COMMENT':
            for line_text in value:
                entries.append(("_comment", line_text, None))
        elif kw is not None:
            # Resolve format spec: runtime override > model default.
            spec = next(
                (m.format_spec for m in field_info.metadata if isinstance(m, FieldMetadata)),
                None,
            )
            if options and options.float_formats and kw in options.float_formats:
                spec = options.float_formats[kw]
            entries.append((kw, value, spec))
        elif isinstance(value, dict):
            for k, v in value.items():
                entries.append(("_user", k, v))
        # else: field has no FieldMetadata and is not a dict → skip.

    # Phase 2 — write.
    if align:
        max_width = max(
            (len(kw) for kw, _, _ in entries if kw not in ("_comment", "_user")),
            default=0,
        )
    else:
        max_width = 0

    for kw, value, spec in entries:
        if kw == "_comment":
            # §7.8.5 — every comment line begins with the COMMENT keyword.
            out.write(f"COMMENT {value}\n")
        elif kw == "_user":
            # USER_DEFINED_x pattern — spec §3.2.4.12, §4.2.4.10, §6.2.11.1.
            user_kw = f"USER_DEFINED_{value}"
            if align:
                user_kw = f"{user_kw:{max_width}}"
            out.write(f"{user_kw} = {spec}\n")  # spec holds the value here
        else:
            padded_kw = f"{kw:{max_width}}" if align else kw
            out.write(f"{padded_kw} = {format_value(value, spec)}\n")


def emit_block(
    model: BaseModel,
    out: TextIO,
    *,
    extra_lines: list[str] | None = None,
    options: "WriterOptions | None" = None,
) -> None:
    """
    Write a complete named block for model.

    If model carries a _delineation ClassVar (OEM.Segment.Metadata,
    OCM.TrajectoryStateBlock, …), the block is wrapped in its START/STOP
    keywords.  For flat models without Delineation (OPM.Metadata, etc.)
    the KVs are written with no delimiters.

    extra_lines, if provided, are written verbatim after the KV pairs but
    before the STOP keyword.  Used for OCM/OEM raw data rows (trajectory
    states, maneuver lines, covariance rows) that are stored as list[str]
    without FieldMetadata.
    """
    delineation = get_delineation(type(model))
    if delineation:
        out.write(f"{delineation.start}\n")
    emit_kvs(model, out, options=options)
    if extra_lines:
        for line in extra_lines:
            out.write(f"{line}\n")
    if delineation:
        out.write(f"{delineation.stop}\n")
