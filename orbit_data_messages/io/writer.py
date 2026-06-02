"""
Format inference: ``.xml`` extension -> XML; everything else -> KVN.

Examples:
    write(msg, "output.oem")               # Auto-detect format and message type
    write(msg, "output.xml")               # Auto-detect format and message type
    write(msg, "output.txt", fmt="kvn")    # Explicit format override
    write_oem(oem, "output.xml")           # Type-specific writer
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.io.registry import get_writer
from orbit_data_messages.models.base import CCSDSDataMessage
from orbit_data_messages.models.oem import OEM
from orbit_data_messages.models.ocm import OCM
from orbit_data_messages.models.omm import OMM
from orbit_data_messages.models.opm import OPM

_CLASS_TO_TYPE: dict[type, str] = {
    OEM: "oem",
    OMM: "omm",
    OPM: "opm",
    OCM: "ocm",
}


def _message_type(message: CCSDSDataMessage) -> str:
    msg_type: str | None = _CLASS_TO_TYPE.get(type(message))
    if msg_type is None:
        known: str = ", ".join(
            cls.__name__ for cls in sorted(_CLASS_TO_TYPE, key=lambda c: c.__name__)
        )
        raise TypeError(
            f"Cannot determine message type for {type(message).__name__!r}. "
            f"Expected one of: {known}."
        )
    return msg_type


def _infer_fmt(
    path: Path, 
    fmt: str | None,
) -> str:
    """
    Infer the format from the file extension.
    """
    return (
        fmt if fmt is not None else (
            "xml" if path.suffix.lower() == ".xml" else "kvn"
        )
    )


def write(
    message: CCSDSDataMessage,
    path: str | Path,
    *,
    fmt: str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Serialize a ``CCSDSDataMessage`` to ``path``.

    When ``fmt`` is omitted, the output format is inferred from the file
    extension: ``.xml`` produces XML; all other extensions produce KVN.

    Args:
        message (CCSDSDataMessage): Validated domain model instance — ``OEM``, ``OMM``, ``OPM``, or ``OCM``.
        path (str | Path): Destination file. Accepts ``str`` or ``Path``. Created or overwritten.
        fmt (str | None): Format override — ``'kvn'`` or ``'xml'``. Auto-inferred when omitted.
        options (WriterOptions | None): Formatting options. ``WriterOptions()`` defaults apply when omitted.

    Raises:
        TypeError: If the concrete type of ``message`` is not a recognized
            CCSDS message class (``OEM``, ``OMM``, ``OPM``, ``OCM``).
        ValueError: If the ``(fmt, message_type)`` pair is not registered.

    Example:
        >>> write(msg, "output.oem")
        >>> write(msg, "output.xml")
        >>> write(msg, "output.txt", fmt="kvn")
    """
    path: Path = Path(path)
    get_writer(
        _infer_fmt(path, fmt),
        _message_type(message),
    ).write(
        message, path, options=options or WriterOptions()
    )


def write_oem(
    message: OEM,
    path: str | Path,
    *,
    fmt: str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OEM message to ``path``. Infers KVN or XML from file extension.
    """
    path: Path = Path(path)
    get_writer(
        _infer_fmt(path, fmt),
        "oem",
    ).write(
        message,
        path,
        options=options or WriterOptions(),
    )


def write_opm(
    message: OPM,
    path: str | Path,
    *,
    fmt: str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OPM message to ``path``. Infers KVN or XML from file extension.
    """
    path: Path = Path(path)
    get_writer(
        _infer_fmt(path, fmt),
        "opm",
    ).write(
        message,
        path,
        options=options or WriterOptions(),
    )


def write_omm(
    message: OMM,
    path: str | Path,
    *,
    fmt: str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OMM message to ``path``. Infers KVN or XML from file extension.
    """
    path: Path = Path(path)
    get_writer(
        _infer_fmt(path, fmt),
        "omm",
    ).write(
        message,
        path,
        options=options or WriterOptions(),
    )


def write_ocm(
    message: OCM,
    path: str | Path,
    *,
    fmt: str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OCM message to ``path``. Infers KVN or XML from file extension.
    """
    path: Path = Path(path)
    get_writer(
        _infer_fmt(path, fmt),
        "ocm",
    ).write(
        message,
        path,
        options=options or WriterOptions(),
    )
