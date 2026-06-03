"""
Serialize CCSDS ODM messages to files or in-memory strings.

Format inference for file output: ``.xml`` extension -> XML; everything else -> KVN.

Examples:
    write(msg, "output.oem")                        # infer format from extension
    write(msg, "output.xml")                        # XML
    write(msg, "output.txt", fmt="kvn")             # explicit override
    write(msg, "output.txt", fmt=MessageFormat.KVN) # typed override
    content = write_string(msg, MessageFormat.KVN)  # in-memory, no file
    write_oem(oem, "output.xml")                    # type-specific writer
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.format import MessageFormat
from orbit_data_messages.io.format import MessageType  # noqa: F401 (re-exported)
from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.io.registry import get_writer
from orbit_data_messages.models.base import CCSDSDataMessage
from orbit_data_messages.models.oem import OEM
from orbit_data_messages.models.ocm import OCM
from orbit_data_messages.models.omm import OMM
from orbit_data_messages.models.opm import OPM


def _message_type(message: CCSDSDataMessage) -> str:
    """
    Derive the registry message-type key from the model's ``_xml_tag``.

    Args:
        message (CCSDSDataMessage): The validated domain model instance.

    Returns:
        str: The message type string.
    """
    tag: str | None = getattr(type(message), "_xml_tag", None)
    if not isinstance(tag, str):
        raise TypeError(
            f"Cannot determine message type for {type(message).__name__!r}. "
            "Expected a CCSDSDataMessage subclass with an '_xml_tag' class variable."
        )
    return tag


def _infer_fmt(path: Path, fmt: MessageFormat | str | None) -> str:
    if fmt is not None:
        return str(fmt).strip().lower()
    return MessageFormat.XML if path.suffix.lower() == ".xml" else MessageFormat.KVN


def write(
    message: CCSDSDataMessage,
    destination: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Serialize a ``CCSDSDataMessage`` to a file.

    Format is inferred from the file extension when ``fmt`` is omitted:
    ``.xml`` -> XML, everything else -> KVN.

    Args:
        message (CCSDSDataMessage): The validated domain model instance.
        destination (str | Path): The destination file. Created or overwritten.
        fmt (MessageFormat | str | None, optional): The format override.
            Auto-inferred from file extension when omitted. Defaults to None.
        options (WriterOptions | None, optional): The formatting options.
            ``WriterOptions()`` defaults apply when omitted. Defaults to None.

    Raises:
        TypeError: If the concrete type of ``message`` is not a recognized
            CCSDS message class.
        ValueError: If the ``(fmt, message_type)`` pair is not registered.

    Example:
        >>> write(msg, "output.oem")
        >>> write(msg, "output.xml", options=WriterOptions(include_units=False))
    """
    path: Path = Path(destination)
    get_writer(_infer_fmt(path, fmt), _message_type(message)).write(
        message,
        path,
        options=options,
    )


def write_string(
    message: CCSDSDataMessage,
    fmt: MessageFormat | str,
    *,
    options: WriterOptions | None = None,
) -> str:
    """
    Serialize a ``CCSDSDataMessage`` to a string without writing to disk.

    Args:
        message (CCSDSDataMessage): The validated domain model instance.
        fmt (MessageFormat | str): The output format — ``MessageFormat.KVN`` or
            ``MessageFormat.XML``.
        options (WriterOptions | None): The formatting options.

    Returns:
        str: The serialized content.

    Example:
        >>> kvn = write_string(opm, MessageFormat.KVN)
        >>> xml = write_string(opm, "xml")
    """
    resolved_fmt: str = str(fmt).strip().lower()
    return get_writer(resolved_fmt, _message_type(message)).write_string(
        message,
        options=options,
    )


def write_oem(
    message: OEM,
    destination: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OEM message to ``destination``. Infers KVN or XML from file extension.

    Args:
        message (OEM): The validated OEM instance.
        destination (str | Path): The destination file. Created or overwritten.
        fmt (MessageFormat | str | None, optional): The format override.
        options (WriterOptions | None, optional): The formatting options.
    """
    path: Path = Path(destination)
    get_writer(_infer_fmt(path, fmt), MessageType.OEM).write(message, path, options=options)


def write_opm(
    message: OPM,
    destination: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OPM message to ``destination``. Infers KVN or XML from file extension.

    Args:
        message (OPM): The validated OPM instance.
        destination (str | Path): The destination file. Created or overwritten.
        fmt (MessageFormat | str | None, optional): The format override.
        options (WriterOptions | None, optional): The formatting options.
    """
    path: Path = Path(destination)
    get_writer(_infer_fmt(path, fmt), MessageType.OPM).write(message, path, options=options)


def write_omm(
    message: OMM,
    destination: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OMM message to ``destination``. Infers KVN or XML from file extension.

    Args:
        message (OMM): The validated OMM instance.
        destination (str | Path): The destination file. Created or overwritten.
        fmt (MessageFormat | str | None, optional): The format override.
        options (WriterOptions | None, optional): The formatting options.
    """
    path: Path = Path(destination)
    get_writer(_infer_fmt(path, fmt), MessageType.OMM).write(message, path, options=options)


def write_ocm(
    message: OCM,
    destination: str | Path,
    *,
    fmt: MessageFormat | str | None = None,
    options: WriterOptions | None = None,
) -> None:
    """
    Write an OCM message to ``destination``. Infers KVN or XML from file extension.

    Args:
        message (OCM): The validated OCM instance.
        destination (str | Path): The destination file. Created or overwritten.
        fmt (MessageFormat | str | None, optional): The format override.
        options (WriterOptions | None, optional): The formatting options.
    """
    path: Path = Path(destination)
    get_writer(_infer_fmt(path, fmt), MessageType.OCM).write(message, path, options=options)
