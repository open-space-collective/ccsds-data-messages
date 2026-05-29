"""
Adapter registry for CCSDS Orbit Data Message I/O.

Maps (format, message_type) pairs to reader and writer adapter classes using
lazy string references — no adapter module is imported at registry load time.
Adapter classes are lazily imported on first request.

Adding a new adapter requires one new entry in _READERS or _WRITERS only.

Example:
    >>> reader = get_reader("kvn", "oem")   # returns KVNOEMReader()
    >>> writer = get_writer("kvn", "opm")   # returns KVNOPMWriter()
"""
from __future__ import annotations

import importlib

# ---------------------------------------------------------------------------
# Registry tables
#
# Each value is "module_path:ClassName" — the class is imported and
# instantiated on first request, not at module load time.
# ---------------------------------------------------------------------------

_READERS: dict[tuple[str, str], str] = {
    ("kvn", "oem"): "orbit_data_messages.io.kvn.oem_reader:KVNOEMReader",
    ("kvn", "omm"): "orbit_data_messages.io.kvn.omm_reader:KVNOMMReader",
    ("kvn", "opm"): "orbit_data_messages.io.kvn.opm_reader:KVNOPMReader",
    ("kvn", "ocm"): "orbit_data_messages.io.kvn.ocm_reader:KVNOCMReader",
    ("xml", "oem"): "orbit_data_messages.io.xml.oem_reader:XMLOEMReader",
    ("xml", "omm"): "orbit_data_messages.io.xml.omm_reader:XMLOMMReader",
    ("xml", "opm"): "orbit_data_messages.io.xml.opm_reader:XMLOPMReader",
    ("xml", "ocm"): "orbit_data_messages.io.xml.ocm_reader:XMLOCMReader",
}

_WRITERS: dict[tuple[str, str], str] = {
    ("kvn", "oem"): "orbit_data_messages.io.kvn.oem_writer:KVNOEMWriter",
    ("kvn", "omm"): "orbit_data_messages.io.kvn.omm_writer:KVNOMMWriter",
    ("kvn", "opm"): "orbit_data_messages.io.kvn.opm_writer:KVNOPMWriter",
    ("kvn", "ocm"): "orbit_data_messages.io.kvn.ocm_writer:KVNOCMWriter",
    ("xml", "oem"): "orbit_data_messages.io.xml.oem_writer:XMLOEMWriter",
    ("xml", "omm"): "orbit_data_messages.io.xml.omm_writer:XMLOMMWriter",
    ("xml", "opm"): "orbit_data_messages.io.xml.opm_writer:XMLOPMWriter",
    ("xml", "ocm"): "orbit_data_messages.io.xml.ocm_writer:XMLOCMWriter",
}


# ---------------------------------------------------------------------------
# Internal loader
# ---------------------------------------------------------------------------

def _load(reference: str) -> object:
    """Resolve a 'module_path:ClassName' string, import the module, and return a fresh instance.

    Python's import machinery caches the module after the first import, so
    subsequent calls are cheap.

    Args:
        reference: A string of the form ``"module.path:ClassName"``.

    Returns:
        A freshly instantiated adapter object of the named class.
    """
    module_path, class_name = reference.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_reader(fmt: str, msg_type: str) -> object:
    """Return an instantiated reader adapter for the given format and message type.

    Args:
        fmt: File format — ``'kvn'`` or ``'xml'``.
        msg_type: CCSDS message type — ``'oem'``, ``'omm'``, ``'opm'``, or ``'ocm'``.

    Returns:
        A freshly instantiated reader adapter satisfying ``MessageReaderPort``.

    Raises:
        ValueError: If the (fmt, msg_type) pair is not registered. The error
            message lists all currently registered combinations.
    """
    key = (fmt, msg_type)
    reference = _READERS.get(key)
    if reference is None:
        available = ", ".join(f"({f!r}, {t!r})" for f, t in sorted(_READERS))
        raise ValueError(
            f"No reader registered for format={fmt!r}, message_type={msg_type!r}. "
            f"Available: {available}"
        )
    return _load(reference)


def get_writer(fmt: str, msg_type: str) -> object:
    """Return an instantiated writer adapter for the given format and message type.

    Args:
        fmt: File format — ``'kvn'`` or ``'xml'``.
        msg_type: CCSDS message type — ``'oem'``, ``'omm'``, ``'opm'``, or ``'ocm'``.

    Returns:
        A freshly instantiated writer adapter satisfying ``MessageWriterPort``.

    Raises:
        ValueError: If the (fmt, msg_type) pair is not registered. The error
            message lists all currently registered combinations.
    """
    key = (fmt, msg_type)
    reference = _WRITERS.get(key)
    if reference is None:
        available = ", ".join(f"({f!r}, {t!r})" for f, t in sorted(_WRITERS))
        raise ValueError(
            f"No writer registered for format={fmt!r}, message_type={msg_type!r}. "
            f"Available: {available}"
        )
    return _load(reference)
