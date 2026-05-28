"""
Writer facade for CCSDS Orbit Data Messages.

Users interact only with this class.  Format inference, adapter selection,
and serialisation are invisible.

    Writer.write(msg, "output.oem")          # KVN inferred from extension
    Writer.write(msg, "output.xml")          # XML inferred from extension
    Writer.write(msg, "output.txt", fmt="kvn")  # explicit format
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.detection import detect_format
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
    """
    Static-method facade for writing CCSDS Orbit Data Messages.

    Accepts str or Path for the path argument.  When fmt is omitted, the
    output format is inferred from the file extension (.xml → xml; everything
    else → kvn).
    """

    @staticmethod
    def write(
        message: CCSDSDataMessage,
        path: str | Path,
        *,
        fmt: str | None = None,
    ) -> None:
        """
        Serialise a CCSDS Orbit Data Message to path.

        Parameters
        ----------
        message : validated domain model (OEM, OMM, OPM, or OCM instance)
        path    : output file (str or Path)
        fmt     : 'kvn' | 'xml' — overrides format inference when provided.
                  When omitted, the format is inferred from the file extension
                  (.xml → xml; .oem/.omm/.opm/.ocm/.txt/… → kvn).
        """
        path = Path(path)

        if fmt is None:
            fmt = detect_format(path)

        msg_type = _message_type(message)
        adapter = get_writer(fmt, msg_type)
        adapter.write(message, path)
