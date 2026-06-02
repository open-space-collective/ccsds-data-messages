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

if TYPE_CHECKING:
    from orbit_data_messages.io.ports import MessageReaderPort
    from orbit_data_messages.io.ports import MessageWriterPort

# Registry tables: each value is a string reference to a reader or writer adapter class,
# lazily imported on first request.
_READERS: dict[tuple[str, str], str | type] = {
    ("kvn", "oem"): "orbit_data_messages.io.kvn.oem_reader:KVNOEMReader",
    ("kvn", "omm"): "orbit_data_messages.io.kvn.omm_reader:KVNOMMReader",
    ("kvn", "opm"): "orbit_data_messages.io.kvn.opm_reader:KVNOPMReader",
    ("kvn", "ocm"): "orbit_data_messages.io.kvn.ocm_reader:KVNOCMReader",
    ("xml", "oem"): "orbit_data_messages.io.xml.oem_reader:XMLOEMReader",
    ("xml", "omm"): "orbit_data_messages.io.xml.omm_reader:XMLOMMReader",
    ("xml", "opm"): "orbit_data_messages.io.xml.opm_reader:XMLOPMReader",
    ("xml", "ocm"): "orbit_data_messages.io.xml.ocm_reader:XMLOCMReader",
}

_WRITERS: dict[tuple[str, str], str | type] = {
    ("kvn", "oem"): "orbit_data_messages.io.kvn.oem_writer:KVNOEMWriter",
    ("kvn", "omm"): "orbit_data_messages.io.kvn.omm_writer:KVNOMMWriter",
    ("kvn", "opm"): "orbit_data_messages.io.kvn.opm_writer:KVNOPMWriter",
    ("kvn", "ocm"): "orbit_data_messages.io.kvn.ocm_writer:KVNOCMWriter",
    ("xml", "oem"): "orbit_data_messages.io.xml.oem_writer:XMLOEMWriter",
    ("xml", "omm"): "orbit_data_messages.io.xml.omm_writer:XMLOMMWriter",
    ("xml", "opm"): "orbit_data_messages.io.xml.opm_writer:XMLOPMWriter",
    ("xml", "ocm"): "orbit_data_messages.io.xml.ocm_writer:XMLOCMWriter",
}


def _load(reference: str | type) -> object:
    if isinstance(reference, type):
        return reference()
    module_path, class_name = reference.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def get_reader(fmt: str, msg_type: str) -> MessageReaderPort:
    """
    Return an instantiated reader adapter for the given ``format`` and ``message_type``.

    Raises:
        ValueError: If the ``(fmt, msg_type)`` pair is not registered.
    """
    reference = _READERS.get((fmt, msg_type))
    if reference is None:
        available = ", ".join(f"({f!r}, {t!r})" for f, t in sorted(_READERS))
        raise ValueError(
            f"No reader registered for format={fmt!r}, message_type={msg_type!r}. "
            f"Available: {available}"
        )
    return _load(reference)  # type: ignore[return-value]


def get_writer(fmt: str, msg_type: str) -> MessageWriterPort:
    """
    Return an instantiated writer adapter for the given ``format`` and ``message_type``.

    Raises:
        ValueError: If the ``(fmt, msg_type)`` pair is not registered.
    """
    reference = _WRITERS.get((fmt, msg_type))
    if reference is None:
        available = ", ".join(f"({f!r}, {t!r})" for f, t in sorted(_WRITERS))
        raise ValueError(
            f"No writer registered for format={fmt!r}, message_type={msg_type!r}. "
            f"Available: {available}"
        )
    return _load(reference)  # type: ignore[return-value]


def register_reader(
    fmt: str, 
    msg_type: str, 
    cls: type[MessageReaderPort],
) -> None:
    """
    Register a custom reader adapter for a ``(format, message_type)`` pair.

    Allows third-party code to extend the registry without modifying built-in
    tables. Overwrites any existing entry for the same key.

    Args:
        fmt (str): The file format string (e.g. ``'kvn'``, ``'xml'``, or a custom name).
        msg_type (str): The message type string (e.g. ``'oem'``, or a custom type).
        cls (type[MessageReaderPort]): The adapter class satisfying ``MessageReaderPort``. Must be a class,
            not an instance; it will be instantiated fresh on each call to ``get_reader()``.
    """
    _READERS[(fmt, msg_type)] = cls


def register_writer(
    fmt: str, 
    msg_type: str, 
    cls: type[MessageWriterPort],
) -> None:
    """
    Register a custom writer adapter for a ``(format, message_type)`` pair.

    Allows third-party code to extend the registry without modifying built-in
    tables. Overwrites any existing entry for the same key.

    Args:
        fmt (str): The file format string (e.g. ``'kvn'``, ``'xml'``, or a custom name).
        msg_type (str): The message type string (e.g. ``'oem'``, or a custom type).
        cls (type[MessageWriterPort]): The adapter class satisfying ``MessageWriterPort``. Must be a class,
            not an instance; it will be instantiated fresh on each call to ``get_writer()``.
    """
    _WRITERS[(fmt, msg_type)] = cls
