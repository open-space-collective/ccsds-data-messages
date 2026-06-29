# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models import CCSDSDataMessage


class MessageReaderPort(Protocol):
    def read(
        self,
        path: Path,
    ) -> CCSDSDataMessage:
        ...

    def read_string(
        self,
        content: str,
    ) -> CCSDSDataMessage:
        ...


class MessageWriterPort(Protocol):
    def write(
        self,
        message: CCSDSDataMessage,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None: ...

    def write_string(
        self,
        message: CCSDSDataMessage,
        *,
        options: WriterOptions | None = None,
    ) -> str: ...
