from __future__ import annotations

from pathlib import Path
from typing import Protocol

from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.models.base import CCSDSDataMessage


class MessageReaderPort(Protocol):
    """
    Structural protocol for ``CCSDSDataMessage`` file readers.
    """

    def read(self, path: Path) -> CCSDSDataMessage: ...


class MessageWriterPort(Protocol):
    """
    Structural protocol for ``CCSDSDataMessage`` file writers.
    """

    def write(
        self,
        message: CCSDSDataMessage,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None: ...
