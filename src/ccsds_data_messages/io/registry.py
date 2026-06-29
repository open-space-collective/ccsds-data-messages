"""
Maps (format, message_type) pairs to reader and writer adapter classes using
lazy string references: no adapter module is imported at registry load time.
Adapter classes are lazily imported on first request.

Adding a built-in adapter requires one new entry in ``_READERS`` or ``_WRITERS`` only.
Alternatively, third-party adapters can be registered at runtime via ``register_reader`` /
``register_writer``, which accept a direct class (not a string reference).
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from typing import TypeAlias
from typing import TypeVar
from typing import cast

from ccsds_data_messages.exceptions import UnsupportedAdapterError
from ccsds_data_messages.io.format import MessageFormat
from ccsds_data_messages.io.format import MessageType

if TYPE_CHECKING:
    from ccsds_data_messages.io.ports import MessageReaderPort
    from ccsds_data_messages.io.ports import MessageWriterPort

AdapterKey: TypeAlias = tuple[str, str]
ReaderReference: TypeAlias = str | type[MessageReaderPort]
WriterReference: TypeAlias = str | type[MessageWriterPort]

# Registry tables: each value is a string reference to a reader or writer adapter class,
# lazily imported on first request. Instantiated adapters are cached. Adapters are
# stateless singletons so a single instance per (fmt, msg_type) pair is sufficient.
_READERS: dict[AdapterKey, ReaderReference] = {
    (MessageFormat.KVN, MessageType.OEM): "ccsds_data_messages.io.kvn.oem_reader:KVNOEMReader",
    (MessageFormat.KVN, MessageType.OMM): "ccsds_data_messages.io.kvn.omm_reader:KVNOMMReader",
    (MessageFormat.KVN, MessageType.OPM): "ccsds_data_messages.io.kvn.opm_reader:KVNOPMReader",
    (MessageFormat.KVN, MessageType.OCM): "ccsds_data_messages.io.kvn.ocm_reader:KVNOCMReader",
    (MessageFormat.XML, MessageType.OEM): "ccsds_data_messages.io.xml.oem_reader:XMLOEMReader",
    (MessageFormat.XML, MessageType.OMM): "ccsds_data_messages.io.xml.omm_reader:XMLOMMReader",
    (MessageFormat.XML, MessageType.OPM): "ccsds_data_messages.io.xml.opm_reader:XMLOPMReader",
    (MessageFormat.XML, MessageType.OCM): "ccsds_data_messages.io.xml.ocm_reader:XMLOCMReader",
}

_WRITERS: dict[AdapterKey, WriterReference] = {
    (MessageFormat.KVN, MessageType.OEM): "ccsds_data_messages.io.kvn.oem_writer:KVNOEMWriter",
    (MessageFormat.KVN, MessageType.OMM): "ccsds_data_messages.io.kvn.omm_writer:KVNOMMWriter",
    (MessageFormat.KVN, MessageType.OPM): "ccsds_data_messages.io.kvn.opm_writer:KVNOPMWriter",
    (MessageFormat.KVN, MessageType.OCM): "ccsds_data_messages.io.kvn.ocm_writer:KVNOCMWriter",
    (MessageFormat.XML, MessageType.OEM): "ccsds_data_messages.io.xml.oem_writer:XMLOEMWriter",
    (MessageFormat.XML, MessageType.OMM): "ccsds_data_messages.io.xml.omm_writer:XMLOMMWriter",
    (MessageFormat.XML, MessageType.OPM): "ccsds_data_messages.io.xml.opm_writer:XMLOPMWriter",
    (MessageFormat.XML, MessageType.OCM): "ccsds_data_messages.io.xml.ocm_writer:XMLOCMWriter",
}

_reader_cache: dict[AdapterKey, MessageReaderPort] = {}
_writer_cache: dict[AdapterKey, MessageWriterPort] = {}

T = TypeVar("T")


def _adapter_key(
    fmt: MessageFormat | str,
    msg_type: MessageType | str,
) -> AdapterKey:
    return (str(fmt).strip().lower(), str(msg_type).strip().lower())


def _instantiate(reference: str | type[T]) -> T:
    if isinstance(reference, type):
        return reference()
    module_path, class_name = reference.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return cast(T, getattr(module, class_name)())


def get_reader(
    fmt: MessageFormat | str,
    msg_type: MessageType | str,
) -> MessageReaderPort:
    """
    Return a cached reader adapter for the given ``format`` and ``message_type``.

    Adapters are stateless; a single instance per key is created on first access
    and reused on subsequent calls.

    Args:
        fmt (MessageFormat | str): The file format (e.g. ``MessageFormat.KVN``,
            ``'kvn'``, or a custom name).
        msg_type (MessageType | str): The message type (e.g. ``MessageType.OEM``,
            ``'oem'``, or a custom type).

    Returns:
        MessageReaderPort: The cached reader adapter.

    Raises:
        UnsupportedAdapterError: If the ``(fmt, msg_type)`` pair is not registered.
    """
    key: AdapterKey = _adapter_key(fmt, msg_type)
    if key not in _reader_cache:
        reference: ReaderReference | None = _READERS.get(key)
        if reference is None:
            available: str = ", ".join(f"({f!r}, {t!r})" for f, t in sorted(_READERS))
            raise UnsupportedAdapterError(
                f"No reader registered for format={fmt!r}, message_type={msg_type!r}. "
                f"Available: {available}"
            )
        _reader_cache[key] = _instantiate(reference)
    return _reader_cache[key]


def get_writer(
    fmt: MessageFormat | str,
    msg_type: MessageType | str,
) -> MessageWriterPort:
    """
    Return a cached writer adapter for the given ``format`` and ``message_type``.

    Adapters are stateless; a single instance per key is created on first access
    and reused on subsequent calls.

    Args:
        fmt (MessageFormat | str): The file format (e.g. ``MessageFormat.KVN``,
            ``'kvn'``, or a custom name).
        msg_type (MessageType | str): The message type (e.g. ``MessageType.OEM``,
            ``'oem'``, or a custom type).

    Returns:
        MessageWriterPort: The cached writer adapter.

    Raises:
        UnsupportedAdapterError: If the ``(fmt, msg_type)`` pair is not registered.
    """
    key: AdapterKey = _adapter_key(fmt, msg_type)
    if key not in _writer_cache:
        reference: WriterReference | None = _WRITERS.get(key)
        if reference is None:
            available: str = ", ".join(f"({f!r}, {t!r})" for f, t in sorted(_WRITERS))
            raise UnsupportedAdapterError(
                f"No writer registered for format={fmt!r}, message_type={msg_type!r}. "
                f"Available: {available}"
            )
        _writer_cache[key] = _instantiate(reference)
    return _writer_cache[key]


def register_reader(
    fmt: MessageFormat | str,
    msg_type: MessageType | str,
    cls: type[MessageReaderPort],
) -> None:
    """
    Register a custom reader adapter for a ``(format, message_type)`` pair.

    Allows third-party code to extend the registry without modifying built-in
    tables. Overwrites any existing entry for the same key.

    Args:
        fmt (MessageFormat | str): The file format (e.g. ``MessageFormat.KVN``,
            ``'kvn'``, or a custom name).
        msg_type (MessageType | str): The message type (e.g. ``MessageType.OEM``,
            ``'oem'``, or a custom type).
        cls (type[MessageReaderPort]): The adapter class satisfying ``MessageReaderPort``.
            Must be a class, not an instance; a single instance is created and cached
            on the first subsequent call to ``get_reader()``.
    """
    key: AdapterKey = _adapter_key(fmt, msg_type)
    _READERS[key] = cls
    _reader_cache.pop(key, None)


def register_writer(
    fmt: MessageFormat | str,
    msg_type: MessageType | str,
    cls: type[MessageWriterPort],
) -> None:
    """
    Register a custom writer adapter for a ``(format, message_type)`` pair.

    Allows third-party code to extend the registry without modifying built-in
    tables. Overwrites any existing entry for the same key.

    Args:
        fmt (MessageFormat | str): The file format (e.g. ``MessageFormat.KVN``,
            ``'kvn'``, or a custom name).
        msg_type (MessageType | str): The message type (e.g. ``MessageType.OEM``,
            ``'oem'``, or a custom type).
        cls (type[MessageWriterPort]): The adapter class satisfying ``MessageWriterPort``.
            Must be a class, not an instance; a single instance is created and cached
            on the first subsequent call to ``get_writer()``.
    """
    key: AdapterKey = _adapter_key(fmt, msg_type)
    _WRITERS[key] = cls
    _writer_cache.pop(key, None)
