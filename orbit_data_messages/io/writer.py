"""Writer facade for CCSDS Orbit Data Messages.

Users interact only with this class. Format inference, adapter selection,
and serialization are invisible.

Example:
    Writer.write(msg, "output.oem")               # KVN inferred from extension
    Writer.write(msg, "output.xml")               # XML inferred from extension
    Writer.write(msg, "output.txt", fmt="kvn")    # explicit format
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.io.registry import get_writer
from orbit_data_messages.models.base import CCSDSDataMessage

# Map concrete class names to registry message-type keys.
# Class name is the canonical identifier; aliases (OrbitEphemerisMessage etc.)
# do not create new classes, so type(instance).__name__ is always one of these.
_CLASS_TO_TYPE: dict[str, str] = {
    "OEM": "oem",
    "OMM": "omm",
    "OPM": "opm",
    "OCM": "ocm",
}


def _message_type(message: CCSDSDataMessage) -> str:
    """Return the registry message-type key for a domain model instance."""
    cls_name = type(message).__name__
    msg_type = _CLASS_TO_TYPE.get(cls_name)
    if msg_type is None:
        raise TypeError(
            f"Cannot determine message type for {cls_name!r}. "
            f"Expected one of: {', '.join(sorted(_CLASS_TO_TYPE))}."
        )
    return msg_type


class Writer:
    """Static-method facade for writing CCSDS Orbit Data Messages.

    Accepts str or Path for the path argument. When fmt is omitted, the
    output format is inferred from the file extension (.xml -> xml; everything
    else -> kvn).

    No instance state.
    """

    @staticmethod
    def write(
        message: CCSDSDataMessage,
        path: str | Path,
        *,
        fmt: str | None = None,
        options: WriterOptions | None = None,
    ) -> None:
        """Serialize a CCSDS Orbit Data Message to path.

        When fmt is omitted, the output format is inferred from the file
        extension: ``.xml`` produces XML; all other extensions (including
        ``.oem``, ``.omm``, ``.opm``, ``.ocm``, and ``.txt``) produce KVN.
        Providing fmt bypasses extension inference entirely.

        Args:
            message: Validated domain model instance to serialize. Must be
                one of OEM, OMM, OPM, or OCM.
            path: Destination file. Accepts str or Path. The file is
                created or overwritten.
            fmt: Format override. One of ``'kvn'`` or ``'xml'``. When omitted,
                the format is inferred from the file extension.
            options: Formatting options.  When omitted, ``WriterOptions()``
                defaults apply (aligned keywords, units in XML).

        Raises:
            TypeError: If the concrete type of message is not a recognized
                CCSDS message class (OEM, OMM, OPM, OCM).
            ValueError: If fmt (or the inferred format) is not registered for
                the given message type.

        Example:
            >>> Writer.write(msg, "output.oem")
            >>> Writer.write(msg, "output.xml")
            >>> Writer.write(msg, "output.txt", fmt="kvn")
        """
        path = Path(path)

        if fmt is None:
            fmt = "xml" if path.suffix.lower() == ".xml" else "kvn"

        msg_type = _message_type(message)
        adapter = get_writer(fmt, msg_type)
        adapter.write(message, path, options=options or WriterOptions())
