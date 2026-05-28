"""
Reader facade for CCSDS Orbit Data Messages.

Users interact only with this class.  All format detection, adapter selection,
and parsing are invisible.

    msg = Reader.read("file.oem")                          # auto-detect
    msg = Reader.read("data.txt", fmt="kvn", message_type="oem")  # explicit
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.detection import detect_format
from orbit_data_messages.io.detection import detect_message_type
from orbit_data_messages.io.registry import get_reader
from orbit_data_messages.models.base import CCSDSDataMessage


class Reader:
    """
    Static-method facade for reading CCSDS Orbit Data Messages.

    Accepts str or Path for the path argument.  When fmt and message_type are
    both omitted, both are auto-detected (extension → stem keyword → content
    sniff).  Providing both bypasses detection entirely.
    """

    @staticmethod
    def read(
        path: str | Path,
        *,
        fmt: str | None = None,
        message_type: str | None = None,
    ) -> CCSDSDataMessage:
        """
        Read a CCSDS Orbit Data Message from path and return a validated
        domain model.

        Parameters
        ----------
        path         : file to read (str or Path)
        fmt          : 'kvn' | 'xml' — overrides format detection when provided
        message_type : 'oem' | 'omm' | 'opm' | 'ocm' — overrides type
                       detection when provided

        Returns
        -------
        CCSDSDataMessage
            The concrete message type (OEM, OMM, OPM, or OCM) as validated by
            Pydantic.  Pydantic ValidationError is never swallowed.

        Raises
        ------
        ValueError
            If format or message type cannot be determined from the file and
            no explicit override was supplied.
        """
        path = Path(path)

        if fmt is None:
            fmt = detect_format(path)

        if message_type is None:
            message_type = detect_message_type(path, fmt)

        adapter = get_reader(fmt, message_type)
        return adapter.read(path)
