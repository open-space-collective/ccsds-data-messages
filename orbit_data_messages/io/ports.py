"""Structural protocols for CCSDS ODM I/O adapters."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Protocol

from orbit_data_messages.models.base import CCSDSDataMessage

if TYPE_CHECKING:
    from orbit_data_messages.io.options import WriterOptions


class MessageReaderPort(Protocol):
    """Structural protocol for CCSDS ODM file readers.

    Any class with a matching ``read`` signature satisfies this interface
    without explicit inheritance.
    """

    def read(self, path: Path) -> CCSDSDataMessage:
        """Reads a CCSDS ODM file and returns a validated domain model.

        Args:
            path: Path to the input file.

        Returns:
            A fully validated domain model instance.
        """
        ...


class MessageWriterPort(Protocol):
    """Structural protocol for CCSDS ODM file writers.

    Any class with a matching ``write`` signature satisfies this interface
    without explicit inheritance.
    """

    def write(
        self,
        message: CCSDSDataMessage,
        path: Path,
        *,
        options: "WriterOptions | None" = None,
    ) -> None:
        """Serializes a validated domain model to a file.

        Args:
            message: The domain model to serialize.
            path: Destination file path.
            options: Formatting options.  When omitted, ``WriterOptions()``
                defaults apply (aligned keywords, units in XML, spec-compliant
                float precision).
        """
        ...
