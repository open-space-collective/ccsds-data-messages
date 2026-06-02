from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Protocol

from orbit_data_messages.models.base import CCSDSDataMessage

if TYPE_CHECKING:
    from orbit_data_messages.io.options import WriterOptions


class MessageReaderPort(Protocol):
    """
    Structural protocol for ``CCSDSDataMessage`` file readers.

    Any class with a matching ``read`` signature satisfies this interface
    without explicit inheritance.
    """

    def read(
        self,
        path: Path
    ) -> CCSDSDataMessage:
        """
        Read a ``CCSDSDataMessage`` file and return a validated instance.

        Args:
            path (Path): Path to the input file.

        Returns:
            CCSDSDataMessage: A fully validated ``CCSDSDataMessage`` instance.
        """
        ...


class MessageWriterPort(Protocol):
    """
    Structural protocol for ``CCSDSDataMessage`` file writers.

    Any class with a matching ``write`` signature satisfies this interface
    without explicit inheritance.
    """

    def write(
        self,
        message: CCSDSDataMessage,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serializes a validated ``CCSDSDataMessage`` instance to a file.

        Args:
            message (CCSDSDataMessage): The instance to serialize.
            path (Path): The destination file path.
            options (WriterOptions | None): Formatting options. When omitted,
                ``WriterOptions()`` defaults apply (aligned keywords, units in XML,
                spec-compliant float precision).
        """
        ...
