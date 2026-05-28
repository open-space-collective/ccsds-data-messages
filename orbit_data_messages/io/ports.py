from pathlib import Path
from typing import Protocol

from orbit_data_messages.models.base import CCSDSDataMessage


class MessageReaderPort(Protocol):
    def read(self, path: Path) -> CCSDSDataMessage: ...


class MessageWriterPort(Protocol):
    def write(self, message: CCSDSDataMessage, path: Path) -> None: ...
