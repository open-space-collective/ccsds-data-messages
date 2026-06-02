"""
Auto-detection flow: file extension -> filename stem keyword -> content sniff.

Examples:
    msg = read("file.oem")                               # auto-detect
    msg = read("data.txt", fmt="kvn", message_type="oem")
    oem = read_oem("file.oem")                           # type-specific
"""
from __future__ import annotations

from pathlib import Path
from typing import cast

from orbit_data_messages.io.detection import detect_format
from orbit_data_messages.io.detection import detect_message_type
from orbit_data_messages.io.registry import get_reader
from orbit_data_messages.models.base import CCSDSDataMessage
from orbit_data_messages.models.oem import OEM
from orbit_data_messages.models.ocm import OCM
from orbit_data_messages.models.omm import OMM
from orbit_data_messages.models.opm import OPM


def read(
    path: str | Path,
    *,
    fmt: str | None = None,
    message_type: str | None = None,
) -> CCSDSDataMessage:
    """
    Read a ``CCSDSDataMessage`` from ``path`` and return a validated domain model.

    When ``fmt`` and ``message_type`` are both omitted, detection proceeds in priority
    order: file extension, filename stem keyword heuristic, then content sniff.
    Providing both arguments bypasses detection entirely and no file I/O is
    performed for detection purposes. Pydantic ValidationError is never
    swallowed: it propagates to the caller unchanged.

    Args:
        path (str | Path): File to read. Accepts ``str`` or ``Path``.
        fmt (str | None): Format override — ``'kvn'`` or ``'xml'``. Auto-detected when omitted.
        message_type (str | None): Message type override — ``'oem'``, ``'omm'``, ``'opm'``, or
            ``'ocm'``. Auto-detected when omitted.

    Returns:
        The concrete message type (``OEM``, ``OMM``, ``OPM``, or ``OCM``) as a fully
        validated Pydantic domain model instance.

    Raises:
        ValueError: If ``format`` or ``message_type`` cannot be determined from
            the file and no explicit override was supplied.

    Example:
        >>> msg = read("file.oem")
        >>> msg = read("data.txt", fmt="kvn", message_type="oem")
        >>> isinstance(msg, CCSDSDataMessage)
        True
    """
    path: Path = Path(path)
    if fmt is None:
        fmt: str = detect_format(path)
    if message_type is None:
        message_type: str = detect_message_type(path, fmt)
    return get_reader(fmt, message_type).read(path)


def read_oem(
    path: str | Path,
    *,
    fmt: str | None = None,
) -> OEM:
    """
    Read an OEM file and return a validated OEM instance. Auto-detects KVN or XML.
    """
    path: Path = Path(path)
    return cast(
        OEM,
        get_reader(
            fmt if fmt is not None else detect_format(path),
            "oem",
        ).read(path),
    )


def read_opm(
    path: str | Path,
    *,
    fmt: str | None = None,
) -> OPM:
    """
    Read an OPM file and return a validated OPM instance. Auto-detects KVN or XML.
    """
    path: Path = Path(path)
    return cast(
        OPM,
        get_reader(
            fmt if fmt is not None else detect_format(path),
            "opm",
        ).read(path),
    )


def read_omm(
    path: str | Path,
    *,
    fmt: str | None = None,
) -> OMM:
    """
    Read an OMM file and return a validated OMM instance. Auto-detects KVN or XML.
    """
    path: Path = Path(path)
    return cast(
        OMM,
        get_reader(
            fmt if fmt is not None else detect_format(path),
            "omm",
        ).read(path),
    )


def read_ocm(
    path: str | Path,
    *,
    fmt: str | None = None,
) -> OCM:
    """
    Read an OCM file and return a validated OCM instance. Auto-detects KVN or XML.
    """
    path: Path = Path(path)
    return cast(
        OCM,
        get_reader(
            fmt if fmt is not None else detect_format(path),
            "ocm",
        ).read(path),
    )
