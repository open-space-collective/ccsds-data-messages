"""Reader facade for CCSDS Orbit Data Messages.

Users interact only with this class. All format detection, adapter selection,
and parsing are invisible.

Example:
    msg = Reader.read("file.oem")                               # auto-detect
    msg = Reader.read("data.txt", fmt="kvn", message_type="oem")  # explicit
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.detection import detect_format
from orbit_data_messages.io.detection import detect_message_type
from orbit_data_messages.io.registry import get_reader
from orbit_data_messages.models.base import CCSDSDataMessage


class Reader:
    """Static-method facade for reading CCSDS Orbit Data Messages.

    Accepts str or Path for the path argument. When fmt and message_type are
    both omitted, both are auto-detected (extension -> stem keyword -> content
    sniff). Providing both bypasses detection entirely.

    No instance state.
    """

    @staticmethod
    def read(
        path: str | Path,
        *,
        fmt: str | None = None,
        message_type: str | None = None,
    ) -> CCSDSDataMessage:
        """Read a CCSDS Orbit Data Message from path and return a validated domain model.

        When fmt and message_type are both omitted, detection proceeds in priority
        order: file extension, filename stem keyword heuristic, then content sniff.
        Providing both arguments bypasses detection entirely and no file I/O is
        performed for detection purposes. Pydantic ValidationError is never
        swallowed — it propagates to the caller unchanged.

        Args:
            path: File to read. Accepts str or Path.
            fmt: Format override. One of ``'kvn'`` or ``'xml'``. When omitted,
                the format is auto-detected from the file extension or content.
            message_type: Message type override. One of ``'oem'``, ``'omm'``,
                ``'opm'``, or ``'ocm'``. When omitted, the type is auto-detected
                from the file extension, filename stem, or content.

        Returns:
            The concrete message type (OEM, OMM, OPM, or OCM) as a fully
            validated Pydantic domain model instance.

        Raises:
            ValueError: If format or message type cannot be determined from
                the file and no explicit override was supplied.

        Example:
            >>> msg = Reader.read("file.oem")
            >>> msg = Reader.read("data.txt", fmt="kvn", message_type="oem")
            >>> isinstance(msg, CCSDSDataMessage)
            True
        """
        path = Path(path)

        if fmt is None:
            fmt = detect_format(path)

        if message_type is None:
            message_type = detect_message_type(path, fmt)

        adapter = get_reader(fmt, message_type)
        return adapter.read(path)
