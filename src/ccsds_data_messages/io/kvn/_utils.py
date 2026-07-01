"""
KVN-specific line-emission and block-introspection helpers.

Generic model-introspection utilities (``build_keyword_map()``, ``map_kvs()``,
``format_value()``) live in ``io._utils`` and are re-exported here for convenience.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

from ccsds_data_messages.io._utils import build_keyword_map, format_value, map_kvs
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models._fields import Delineation, FieldMetadata

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import BaseModel


# Re-export so callers that import from this module continue to work.
__all__ = [
    "SupportsWrite",
    "block_delimiter_name",
    "block_start_keyword",
    "build_keyword_map",
    "emit_block",
    "emit_kvs",
    "emit_user_defined",
    "field_keyword",
    "format_value",
    "get_delineation",
    "guard_lines",
    "map_kvs",
    "required_block_delimiter_name",
    "to_kwargs",
]


class SupportsWrite(Protocol):
    """The minimal subset of ``TextIO`` that KVN emitters need: ``write``/``writelines``."""

    def write(self, text: str) -> int: ...
    def writelines(self, lines: Iterable[str]) -> None: ...


def to_kwargs(
    keyword_values: dict[str, str],
    field_map: dict[str, str],
    comments: list[str],
) -> dict[str, str | list[str]]:
    """
    Map parsed ``{keyword: value}`` pairs to constructor kwargs via a pre-built field map.

    Unlike ``io._utils.map_kvs``, ``field_map`` is passed in rather than derived from
    ``model_class`` on every call - callers that parse many blocks of the same model
    class (e.g. OPM's/OMM's fully-flat KVN readers) build the field map once at module
    load time and reuse it.

    Args:
        keyword_values (dict[str, str]): Parsed ``{keyword: value}`` pairs from the file.
        field_map (dict[str, str]): ``{keyword: pydantic_field_name}`` for the target model.
        comments (list[str]): Accumulated comment texts to attribute to this block.

    Returns:
        dict[str, str | list[str]]: Constructor kwargs ready for ``model_class(**kwargs)``.
    """
    kwargs: dict[str, str | list[str]] = {
        field_map[kw]: val for kw, val in keyword_values.items() if kw in field_map
    }
    if comments:
        kwargs["comment"] = comments
    return kwargs


# Section 7.3.4: only printable ASCII (0x20-0x7E) is permitted; control characters
# (e.g. TAB) are forbidden, except line terminators, which are never present here
# since each write() call below ends with an explicit "\n" rather than embedding one.
_NON_PRINTABLE_ASCII_RE: re.Pattern[str] = re.compile(r"[^\x20-\x7e]")


class _LineGuardedWriter:
    """
    ``TextIO``-like wrapper enforcing section 7.3.2 and 7.3.4 on every line written.

    Checks line length (7.3.2) and printable-ASCII-only (7.3.4) on every line.
    The writer owns its own output, so violations are programming errors, not
    malformed external input: raise immediately rather than warn.
    """

    def __init__(self, out: SupportsWrite, *, max_line_length: int | None = None) -> None:
        self._out = out
        self._max_line_length = max_line_length

    def write(self, text: str) -> int:
        # Each write() call here is a single line plus a trailing "\n"; split
        # defensively in case a caller ever batches multiple lines in one call.
        for line in text.split("\n"):
            if not line:
                continue
            if self._max_line_length is not None and len(line) > self._max_line_length:
                raise ValueError(
                    f"KVN line is {len(line)} characters, exceeding the "
                    f"{self._max_line_length}-character limit (§7.3.2): {line[:80]!r}..."
                )
            if bad_chars := sorted(set(_NON_PRINTABLE_ASCII_RE.findall(line))):
                raise ValueError(
                    f"KVN line contains non-printable-ASCII or control characters "
                    f"{bad_chars!r} (§7.3.4): {line[:80]!r}..."
                )
        return self._out.write(text)

    def writelines(self, lines: Iterable[str]) -> None:
        # Route through write() per chunk so every line is still checked;
        # TextIO.writelines() is otherwise equivalent to repeated write() calls.
        for text in lines:
            self.write(text)


def guard_lines(
    out: SupportsWrite, *, max_line_length: int | None = None
) -> SupportsWrite:
    """
    Wrap ``out`` so every line written through it is checked (section 7.3.2, 7.3.4).

    Checks line length (7.3.2, when ``max_line_length`` is set) and printable
    ASCII only (7.3.4, always).

    Args:
        out: The underlying text stream to wrap.
        max_line_length: Maximum permitted line length (§7.3.2: 254 for
            OPM/OMM/OEM). Pass None for formats with no limit, e.g. OCM (§7.3.3).

    Returns:
        A ``TextIO``-compatible object; callers can use it as a drop-in
        replacement for ``out``.
    """
    return _LineGuardedWriter(out, max_line_length=max_line_length)


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
    attr: Delineation | None = getattr(model_class, "_delineation", None)
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
    if (delineation := get_delineation(model_class)) is None:
        return None
    return delineation.start.removesuffix("_START")


def required_block_delimiter_name(model_class: type[BaseModel]) -> str:
    """
    Same as ``block_delimiter_name``, but raises instead of returning ``None``.

    For reader/writer module-level constants, a ``None`` result means the model
    class is missing its ``_delineation`` class variable - a programming error in
    this codebase, not a condition that can arise from external input. Raising
    here (at module import time) turns that mistake into an immediate, clear
    failure instead of a delimiter constant that's silently ``None`` and never
    matches any block name.

    Args:
        model_class (type[BaseModel]): Pydantic model class to inspect.

    Returns:
        str: Block-type string (e.g. ``'META'``, ``'COVARIANCE'``).
    """
    if (name := block_delimiter_name(model_class)) is None:
        raise TypeError(
            f"{model_class.__qualname__} has no _delineation class variable; "
            "cannot derive its block delimiter name."
        )
    return name


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


class _Entry(NamedTuple):
    """One pending output line for ``emit_kvs()``: either ``KEYWORD = value`` or a COMMENT."""

    keyword: str
    value: Any
    format_spec: str | None
    is_comment: bool = False


def emit_user_defined(
    user_defined_parameters: dict[str, str],
    output: SupportsWrite,
) -> None:
    """Emit ``USER_DEFINED_x = value`` lines for a user-defined parameters dict."""
    output.writelines(
        f"USER_DEFINED_{suffix} = {value}\n"
        for suffix, value in user_defined_parameters.items()
    )


def emit_kvs(
    model: BaseModel,
    out: SupportsWrite,
    *,
    options: WriterOptions | None = None,
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
        out (SupportsWrite): Destination text stream.
        options (WriterOptions | None): Formatting options. Defaults to None,
            which applies ``WriterOptions()`` defaults.

    Returns:
        None
    """
    keyword_map: dict[str, str] = build_keyword_map(type(model))
    field_to_keyword: dict[str, str] = {fn: kw for kw, fn in keyword_map.items()}
    opts = options if options is not None else WriterOptions()
    align: bool = opts.align_keywords
    suppress: bool = opts.suppress_defaults

    # Phase 1: collect entries.
    # entries: pending KEYWORD = value / COMMENT lines, in declaration order.
    # user_entries: (key_name, value) for USER_DEFINED_* pairs — written last.
    entries: list[_Entry] = []
    user_entries: list[tuple[str, str]] = []

    for field_name, field_info in type(model).model_fields.items():
        if (value := getattr(model, field_name)) is None:
            continue
        if suppress:
            # Currently unreachable with a distinct effect: every optional field's
            # Python default is None, and None values are already skipped above,
            # so `not in model_fields_set` never fires for a non-None value today.
            # Kept for correctness if a future field gains a non-None default.
            if field_name not in model.model_fields_set:
                continue
            spec_default = next(
                (
                    m.spec_default
                    for m in field_info.metadata
                    if isinstance(m, FieldMetadata)
                ),
                None,
            )
            if spec_default is not None and value == spec_default:
                continue

        keyword: str | None = field_to_keyword.get(field_name)

        if keyword == "COMMENT":
            entries.extend(
                _Entry("COMMENT", line_text, None, is_comment=True) for line_text in value
            )
        elif keyword is not None:
            # Resolve format spec: runtime override > model default.
            spec: str | None = next(
                (
                    m.format_spec
                    for m in field_info.metadata
                    if isinstance(m, FieldMetadata)
                ),
                None,
            )
            if opts.float_formats and keyword in opts.float_formats:
                spec = opts.float_formats[keyword]
            entries.append(_Entry(keyword, value, spec))
        elif isinstance(value, dict):
            for k, v in value.items():
                user_entries.append((k, v))
        # else: field has no FieldMetadata and is not a dict -> skip.

    # Phase 2: write.

    # Apply explicit output ordering declared via FieldMetadata.order on each field.
    # Entries without an order annotation default to 50 (neutral). Version keywords
    # (CCSDS_*_VERS) carry order=0 so they sort to the front of every header block,
    # overriding Pydantic's inheritance-first field ordering.
    keyword_order: dict[str, int] = {
        kw: next((m.order for m in fi.metadata if isinstance(m, FieldMetadata)), 50)
        for fi in type(model).model_fields.values()
        for kw in (
            next((m.keyword for m in fi.metadata if isinstance(m, FieldMetadata)), None),
        )
        if kw is not None
    }
    entries.sort(key=lambda entry: keyword_order.get(entry.keyword, 50))

    if align:
        keyword_widths = [len(entry.keyword) for entry in entries if not entry.is_comment]
        keyword_widths += [len(f"USER_DEFINED_{k}") for k, _ in user_entries]
        max_width: int = max(keyword_widths, default=0)
    else:
        max_width: int = 0

    for keyword, value, spec, is_comment in entries:
        if is_comment:
            # section 7.8.5: every comment line begins with the COMMENT keyword.
            out.write(f"COMMENT {value}\n")
        else:
            padded_keyword: str = f"{keyword:{max_width}}" if align else keyword
            out.write(f"{padded_keyword} = {format_value(value, spec)}\n")

    for key_name, user_value in user_entries:
        # USER_DEFINED_x pattern: spec section 3.2.4.12, section 4.2.4.10, section 6.2.11.1.
        user_keyword: str = f"USER_DEFINED_{key_name}"
        if align:
            user_keyword = f"{user_keyword:{max_width}}"
        out.write(f"{user_keyword} = {user_value}\n")


def emit_block(
    model: BaseModel,
    out: SupportsWrite,
    *,
    extra_lines: list[str] | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write a complete KVN block, optionally wrapped in ``*_START``/``*_STOP`` delimiters.

    If ``model`` carries a ``_delineation`` class variable (e.g. ``OEM.Segment.Metadata``, ``OCM.TrajectoryStateTimeHistory``),
    the block is wrapped with its start and stop keywords.
    Flat models without a ``_delineation`` (e.g. ``OPM.Metadata``) are written with no delimiters.

    Args:
        model (BaseModel): Pydantic model instance to serialize.
        out (SupportsWrite): Destination text stream.
        extra_lines (list[str] | None): Raw data rows written verbatim after the
            KV pairs but before the ``*_STOP`` keyword: used for OCM/OEM
            trajectory, covariance, and maneuver lines stored as ``list[str]``
            without ``FieldMetadata``. Defaults to None.
        options (WriterOptions | None): Formatting options. Defaults to None.

    Returns:
        None
    """
    if delineation := get_delineation(type(model)):
        out.write(f"{delineation.start}\n")
    emit_kvs(model, out, options=options)
    if extra_lines:
        out.writelines(f"{line}\n" for line in extra_lines)
    if delineation:
        out.write(f"{delineation.stop}\n")
