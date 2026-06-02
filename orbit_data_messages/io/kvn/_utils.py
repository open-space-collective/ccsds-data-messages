"""
Generic model-introspection utilities (``build_keyword_map()``, ``map_kvs()``, ``format_value()``)
live in ``io._utils`` and are re-exported here for convenience.
"""
from __future__ import annotations

from typing import Any
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
    "block_start_keyword",
    "dispatch_flat_kvs",
    "emit_kvs",
    "emit_block",
]


def get_delineation(model_class: type[BaseModel]) -> Delineation | None:
    """
    Return the ``_delineation`` class variable from a model class, if present.

    Nested block model classes (e.g. ``OEM.Segment.Metadata``) carry a
    ``_delineation: ClassVar[Delineation]`` that names the ``*_START``/``*_STOP``
    keywords for that block.

    Args:
        model_class (type[BaseModel]): Pydantic model class to inspect.

    Returns:
        Delineation | None: The ``Delineation`` instance, or ``None`` when the
        class carries no such class variable.
    """
    attr: Delineation | None = getattr(model_class, '_delineation', None)
    return attr if isinstance(attr, Delineation) else None


def block_delimiter_name(model_class: type[BaseModel]) -> str | None:
    """
    Return the block-type string derived from a model's ``Delineation.start`` attribute.

    Strips the ``_START`` suffix, so ``'META_START'`` becomes ``'META'``.
    This string is used as the ``'delimiter'`` key in ``split_blocks()`` output.

    Args:
        model_class (type[BaseModel]): Pydantic model class to inspect.

    Returns:
        str | None: Block-type string (e.g. ``'META'``, ``'COVARIANCE'``), or
        ``None`` when the class has no ``_delineation`` class variable.
    """
    delineation: Delineation | None = get_delineation(model_class)
    if delineation is None:
        return None
    return delineation.start.removesuffix('_START')


def field_keyword(
    model_class: type[BaseModel],
    field_name: str,
) -> str:
    """
    Return the KVN keyword string for a named field on a model class.

    The only sanctioned way for an adapter to obtain the keyword for a field is to use this function.
    Adapters need to treat structurally (e.g. as a block-separator key).
    The keyword is read from the ``FieldMetadata`` annotation: nothing is hardcoded.

    Args:
        model_class (type[BaseModel]): Pydantic model class that owns the field.
        field_name (str): Python attribute name of the field.

    Returns:
        str: The CCSDS keyword string (e.g. ``'MAN_EPOCH_IGNITION'``).

    Raises:
        ValueError: If ``field_name`` carries no ``FieldMetadata(keyword=...)``.
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


def block_start_keyword(model_class: type[BaseModel]) -> str:
    """
    Return the KVN keyword for the field marked ``block_start=True`` on a model class.

    Adapters call this instead of ``field_keyword(cls, "field_name")`` so that
    the choice of which field begins a repeating block is declared in the model,
    not in the reader/writer.

    Args:
        model_class (type[BaseModel]): Pydantic model class to inspect.

    Returns:
        str: The CCSDS keyword string for the block-start field.

    Raises:
        ValueError: If no field on ``model_class`` carries
            ``FieldMetadata(block_start=True)``.
    """
    for field_info in model_class.model_fields.values():
        for item in field_info.metadata:
            if isinstance(item, FieldMetadata) and item.block_start:
                return item.keyword
    raise ValueError(
        f"{model_class.__qualname__} has no field with FieldMetadata(block_start=True). "
        f"Mark the field that signals the start of a new repeating block."
    )


def dispatch_flat_kvs(
    ordered_items: list[tuple[str, str | None, str | None]],
    block_maps: list[tuple[dict[str, str], dict[str, str], list[str]]],
    *,
    user_kvs: dict[str, str] | None = None,
    maneuver_key: str | None = None,
    maneuver_map: dict[str, str] | None = None,
) -> list[tuple[dict[str, str], list[str]]]:
    """
    Distribute flat KV pairs and comments across named sub-model accumulators.

    Used by ``OPM`` and ``OMM`` KVN readers, which parse a fully flat sequence of
    ``KEY = VALUE`` lines (section 7.4.1: no ``*_START``/``*_STOP`` block delimiters).
    Each ``kvs_dict`` and ``comments_list`` in ``block_maps`` is mutated in place;
    read them after the call to obtain the routed results. ``user_kvs`` is an optional
    accumulator for ``USER_DEFINED_x`` pairs, mutated in place.
    ``maneuver_key`` and ``maneuver_map`` are optional parameters for handling maneuver groups
    (OPM only: OMM has no maneuver section: section 4.2.4.8).

    Args:
        ordered_items (list[tuple[str, str | None, str | None]]): The
            ``header_ordered_items`` list from ``parse_kvn()``, each entry being
            ``(kind, key, value)`` where ``kind`` is ``'kv'``, ``'comment'``,
            or ``'data'``.
        block_maps (list[tuple[dict[str, str], dict[str, str], list[str]]]): One
            ``(keyword_map, kvs_dict, comments_list)`` triple per logical block
            (header, metadata, state-vector, …). ``kvs_dict`` and ``comments_list``
            are mutated in place.
        user_kvs (dict[str, str] | None): Optional accumulator for
            ``USER_DEFINED_x`` pairs, mutated in place. Defaults to None.
        maneuver_key (str | None): When set, a KV pair with this keyword signals
            the start of a new maneuver group; groups are returned rather than
            stored in ``block_maps``. Defaults to None.
        maneuver_map (dict[str, str] | None): Keyword map for the maneuver
            sub-model; required when ``maneuver_key`` is set. Keywords in this map
            are routed to the current maneuver group. Defaults to None.

    Returns:
        list[tuple[dict[str, str], list[str]]]: One ``(kvs, comments)`` tuple per
        detected maneuver group. Empty list when ``maneuver_key`` is ``None`` or no
        groups are found.
    """
    # Build a fast lookup: keyword -> (kvs_dict, comments_list) for each block.
    kw_to_block: dict[str, tuple[dict[str, str], list[str]]] = {}
    for kw_map, kvs_dict, comments_list in block_maps:
        for kw in kw_map:
            kw_to_block[kw] = (kvs_dict, comments_list)

    man_kw_map: dict[str, str] = maneuver_map if maneuver_map is not None else {}

    pending: list[str] = []  # Comments awaiting block assignment.
    man_groups: list[tuple[dict[str, str], list[str]]] = []
    current_man_kvs: dict[str, str] | None = None
    current_man_comments: list[str] = []

    for kind, key, value in ordered_items:
        if kind == "comment":
            pending.append(value)
            continue
        if kind != "kv":
            continue

        if maneuver_key and key == maneuver_key:
            # Seal the previous maneuver group and start a new one.
            if current_man_kvs is not None:
                man_groups.append((current_man_kvs, current_man_comments))
            current_man_kvs: dict[str, str] = {}
            current_man_comments = list(pending)
            pending.clear()
            current_man_kvs[key] = value

        elif current_man_kvs is not None and key in man_kw_map:
            # Continuation of the current maneuver group.
            current_man_comments.extend(pending)
            pending.clear()
            current_man_kvs[key] = value

        elif user_kvs is not None and key.startswith("USER_DEFINED_"):
            pending.clear()
            user_kvs[key] = value

        elif key in kw_to_block:
            kvs_dict, comments_list = kw_to_block[key]
            comments_list.extend(pending)
            pending.clear()
            kvs_dict[key] = value

    # Seal the last maneuver group.
    if current_man_kvs:
        man_groups.append((current_man_kvs, current_man_comments))

    return man_groups


def emit_kvs(
    model: BaseModel,
    out: TextIO,
    *,
    options: "WriterOptions | None" = None,
) -> None:
    """
    Write ``KEY = VALUE`` lines for all non-None fields of a model.

    Field order follows ``model_fields``, preserving the spec-mandated keyword order (section 7.4.8).
    Keywords are read from ``FieldMetadata`` annotations: nothing is hardcoded.
    Special handling: ``COMMENT`` fields become ``COMMENT text`` lines (section 7.8.5);
    ``dict`` fields with no ``FieldMetadata`` become ``USER_DEFINED_k = v`` pairs (section 3.2.4.12);
    other unannotated fields (e.g. ``data_lines``) are silently skipped: callers handle them separately.
    When ``options.align_keywords`` is ``True``, keywords are right-padded so ``=`` signs align in a column (section 7.4.5).

    Args:
        model (BaseModel): Pydantic model instance whose fields will be written.
        out (TextIO): Destination text stream.
        options (WriterOptions | None): Formatting options. Defaults to None,
            which applies ``WriterOptions()`` defaults.

    Returns:
        None
    """
    kw_map: dict[str, str] = build_keyword_map(type(model))
    field_to_kw: dict[str, str] = {fn: kw for kw, fn in kw_map.items()}
    align: bool = options is not None and options.align_keywords

    # Phase 1: collect entries.
    # Each entry is one of:
    #   ("_comment", text, None): COMMENT line
    #   ("_user", "USER_DEFINED_k", value): USER_DEFINED pair
    #   (keyword, value, spec): normal KV pair
    entries: list[tuple[str, Any, Any]] = []

    for field_name, field_info in type(model).model_fields.items():
        value: Any = getattr(model, field_name)
        if value is None:
            continue

        kw: str | None = field_to_kw.get(field_name)

        if kw == "COMMENT":
            for line_text in value:
                entries.append(("_comment", line_text, None))
        elif kw is not None:
            # Resolve format spec: runtime override > model default.
            spec: str | None = next(
                (m.format_spec for m in field_info.metadata if isinstance(m, FieldMetadata)),
                None,
            )
            if options and options.float_formats and kw in options.float_formats:
                spec: str = options.float_formats[kw]
            entries.append((kw, value, spec))
        elif isinstance(value, dict):
            for k, v in value.items():
                entries.append(("_user", k, v))
        # else: field has no FieldMetadata and is not a dict -> skip.

    # Phase 2: write.

    # The spec requires the version keyword (CCSDS_OPM_VERS, CCSDS_OEM_VERS, etc.) to
    # appear first in every header block. When a Header subclass inherits shared fields
    # from CCSDSMessageHeader, Pydantic places the parent's fields (comment, creation_date,
    # ...) before the child's version field in model_fields, which is the reverse of the
    # required output order. We restore the correct order here by moving the version entry
    # to the front, without changing how fields are stored or validated.
    entries.sort(
        key=lambda e: 0 if isinstance(e[0], str) and e[0].startswith("CCSDS_") and e[0].endswith("_VERS") else 1
    )

    if align:
        max_width: int = max(
            (len(kw) for kw, _, _ in entries if kw not in ("_comment", "_user")),
            default=0,
        )
    else:
        max_width: int = 0

    for kw, value, spec in entries:
        if kw == "_comment":
            # section 7.8.5: every comment line begins with the COMMENT keyword.
            out.write(f"COMMENT {value}\n")
        elif kw == "_user":
            # USER_DEFINED_x pattern: spec section 3.2.4.12, section 4.2.4.10, section 6.2.11.1.
            user_kw: str = f"USER_DEFINED_{value}"
            if align:
                user_kw: str = f"{user_kw:{max_width}}"
            out.write(f"{user_kw} = {spec}\n")  # ``spec`` holds the value here
        else:
            padded_kw: str = f"{kw:{max_width}}" if align else kw
            out.write(f"{padded_kw} = {format_value(value, spec)}\n")


def emit_block(
    model: BaseModel,
    out: TextIO,
    *,
    extra_lines: list[str] | None = None,
    options: "WriterOptions | None" = None,
) -> None:
    """
    Write a complete KVN block, optionally wrapped in ``*_START``/``*_STOP`` delimiters.

    If ``model`` carries a ``_delineation`` class variable (e.g. ``OEM.Segment.Metadata``, ``OCM.TrajectoryStateTimeHistory``),
    the block is wrapped with its start and stop keywords.
    Flat models without a ``_delineation`` (e.g. ``OPM.Metadata``) are written with no delimiters.

    Args:
        model (BaseModel): Pydantic model instance to serialize.
        out (TextIO): Destination text stream.
        extra_lines (list[str] | None): Raw data rows written verbatim after the
            KV pairs but before the ``*_STOP`` keyword: used for OCM/OEM
            trajectory, covariance, and maneuver lines stored as ``list[str]``
            without ``FieldMetadata``. Defaults to None.
        options (WriterOptions | None): Formatting options. Defaults to None.

    Returns:
        None
    """
    delineation: Delineation | None = get_delineation(type(model))
    if delineation:
        out.write(f"{delineation.start}\n")
    emit_kvs(model, out, options=options)
    if extra_lines:
        for line in extra_lines:
            out.write(f"{line}\n")
    if delineation:
        out.write(f"{delineation.stop}\n")
