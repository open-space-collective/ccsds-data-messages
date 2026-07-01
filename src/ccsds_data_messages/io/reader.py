# SPDX-License-Identifier: Apache-2.0

"""
Auto-detection flow (file path): file extension -> filename stem keyword -> content sniff.

Examples:
    msg = read("file.oem")                                      # auto-detect
    msg = read("data.txt", fmt="kvn", message_type="oem")
    msg = read("data.txt", fmt=MessageFormat.KVN, message_type=MessageType.OEM)
    oem = read_oem("file.oem")                                  # type-specific, auto-detect format
    msg = read_string(content, MessageFormat.KVN, MessageType.OPM)
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pydantic

from ccsds_data_messages.exceptions import SpecViolationError
from ccsds_data_messages.io._utils import _normalize_fmt, _normalize_type
from ccsds_data_messages.io.detection import detect_format, detect_message_type
from ccsds_data_messages.io.format import MessageFormat, MessageType
from ccsds_data_messages.io.registry import get_reader
from ccsds_data_messages.models import CCSDSDataMessage
from ccsds_data_messages.models.ocm import OCM
from ccsds_data_messages.models.oem import OEM
from ccsds_data_messages.models.omm import OMM
from ccsds_data_messages.models.opm import OPM


def read(
    source: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
    message_type: MessageType | str | None = None,
) -> CCSDSDataMessage:
    """
    Read a ``CCSDSDataMessage`` from a file and return a validated domain model.

    When ``fmt`` and ``message_type`` are both omitted, detection proceeds in
    priority order: file extension, filename stem keyword heuristic, then content
    sniff. Providing both arguments bypasses detection entirely.
    ``pydantic.ValidationError`` is never surfaced to the caller as-is - it is
    caught and re-raised as ``SpecViolationError``.

    Args:
        source (str | Path): The file to read.
        fmt (MessageFormat | str | None, optional): The format override -
            ``MessageFormat.KVN`` or ``MessageFormat.XML`` (plain strings
            ``'kvn'``/``'xml'`` also accepted). Auto-detected when omitted.
            Defaults to None.
        message_type (MessageType | str | None, optional): The message type
            override - ``MessageType.OEM``, ``MessageType.OPM``, etc. (plain
            strings also accepted). Auto-detected when omitted. Defaults to None.

    Returns:
        CCSDSDataMessage: The concrete message type as a fully validated instance.

    Raises:
        DetectionError: If format or message type is omitted and cannot be determined.
        SpecViolationError: If the file content fails domain model validation.

    Example:
        >>> msg = read("file.oem")
        >>> msg = read("data.txt", fmt=MessageFormat.KVN, message_type=MessageType.OPM)
        >>> isinstance(msg, CCSDSDataMessage)
        True
    """
    path: Path = Path(source)
    resolved_fmt: str = _normalize_fmt(fmt) if fmt is not None else detect_format(path)
    resolved_type: str = (
        _normalize_type(message_type)
        if message_type is not None
        else detect_message_type(path, resolved_fmt)
    )
    try:
        return get_reader(resolved_fmt, resolved_type).read(path)
    except pydantic.ValidationError as exc:
        raise SpecViolationError(str(exc)) from exc


def read_string(
    content: str,
    fmt: MessageFormat | str,
    message_type: MessageType | str,
) -> CCSDSDataMessage:
    """
    Parse a ``CCSDSDataMessage`` from an in-memory string.

    Unlike ``read()``, format and message type are mandatory - there is no file
    path to sniff them from.

    Args:
        content (str): The raw KVN or XML content to parse.
        fmt (MessageFormat | str): The wire format - ``MessageFormat.KVN`` or
            ``MessageFormat.XML``.
        message_type (MessageType | str): The message type - ``MessageType.OEM``,
            ``MessageType.OPM``, ``MessageType.OMM``, or ``MessageType.OCM``.

    Returns:
        CCSDSDataMessage: The concrete message type as a fully validated instance.

    Raises:
        UnsupportedAdapterError: If the ``(fmt, message_type)`` pair is not registered.
        SpecViolationError: If the content fails domain model validation.

    Example:
        >>> msg = read_string(kvn_text, MessageFormat.KVN, MessageType.OPM)
        >>> msg = read_string(xml_text, "xml", "oem")
    """
    try:
        return get_reader(
            _normalize_fmt(fmt),
            _normalize_type(message_type),
        ).read_string(content)
    except pydantic.ValidationError as exc:
        raise SpecViolationError(str(exc)) from exc


def read_oem(
    source: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
) -> OEM:
    """
    Read an OEM file and return a validated OEM instance. Auto-detects KVN or XML.

    Args:
        source (str | Path): The file to read.
        fmt (MessageFormat | str | None, optional): The format override -
            ``MessageFormat.KVN`` or ``MessageFormat.XML`` (plain strings
            ``'kvn'``/``'xml'`` also accepted). Auto-detected when omitted.
            Defaults to None.

    Returns:
        OEM: The validated OEM instance.

    Raises:
        SpecViolationError: If the file content fails domain model validation.
    """
    path: Path = Path(source)
    resolved_fmt: str = _normalize_fmt(fmt) if fmt is not None else detect_format(path)
    try:
        return cast("OEM", get_reader(resolved_fmt, MessageType.OEM).read(path))
    except pydantic.ValidationError as exc:
        raise SpecViolationError(str(exc)) from exc


def read_opm(
    source: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
) -> OPM:
    """
    Read an OPM file and return a validated OPM instance. Auto-detects KVN or XML.

    Args:
        source (str | Path): The file to read.
        fmt (MessageFormat | str | None, optional): The format override -
            ``MessageFormat.KVN`` or ``MessageFormat.XML`` (plain strings
            ``'kvn'``/``'xml'`` also accepted). Auto-detected when omitted.
            Defaults to None.

    Returns:
        OPM: The validated OPM instance.

    Raises:
        SpecViolationError: If the file content fails domain model validation.
    """
    path: Path = Path(source)
    resolved_fmt: str = _normalize_fmt(fmt) if fmt is not None else detect_format(path)
    try:
        return cast("OPM", get_reader(resolved_fmt, MessageType.OPM).read(path))
    except pydantic.ValidationError as exc:
        raise SpecViolationError(str(exc)) from exc


def read_omm(
    source: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
) -> OMM:
    """
    Read an OMM file and return a validated OMM instance. Auto-detects KVN or XML.

    Args:
        source (str | Path): The file to read.
        fmt (MessageFormat | str | None, optional): The format override -
            ``MessageFormat.KVN`` or ``MessageFormat.XML`` (plain strings
            ``'kvn'``/``'xml'`` also accepted). Auto-detected when omitted.
            Defaults to None.

    Returns:
        OMM: The validated OMM instance.

    Raises:
        SpecViolationError: If the file content fails domain model validation.
    """
    path: Path = Path(source)
    resolved_fmt: str = _normalize_fmt(fmt) if fmt is not None else detect_format(path)
    try:
        return cast("OMM", get_reader(resolved_fmt, MessageType.OMM).read(path))
    except pydantic.ValidationError as exc:
        raise SpecViolationError(str(exc)) from exc


def read_ocm(
    source: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
) -> OCM:
    """
    Read an OCM file and return a validated OCM instance. Auto-detects KVN or XML.

    Args:
        source (str | Path): The file to read.
        fmt (MessageFormat | str | None, optional): The format override -
            ``MessageFormat.KVN`` or ``MessageFormat.XML`` (plain strings
            ``'kvn'``/``'xml'`` also accepted). Auto-detected when omitted.
            Defaults to None.

    Returns:
        OCM: The validated OCM instance.

    Raises:
        SpecViolationError: If the file content fails domain model validation.
    """
    path: Path = Path(source)
    resolved_fmt: str = _normalize_fmt(fmt) if fmt is not None else detect_format(path)
    try:
        return cast("OCM", get_reader(resolved_fmt, MessageType.OCM).read(path))
    except pydantic.ValidationError as exc:
        raise SpecViolationError(str(exc)) from exc
