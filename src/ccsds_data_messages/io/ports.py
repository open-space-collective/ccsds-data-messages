# SPDX-License-Identifier: Apache-2.0

"""
Reader/writer Protocol interfaces implemented by each format's adapter classes.

``MessageReaderPort`` and ``MessageWriterPort`` define the instance-method shape
every KVN and XML adapter (``io/kvn/*``, ``io/xml/*``) conforms to, so
``io/registry.py`` can cache and dispatch through one uniform interface regardless
of format or message type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models import CCSDSDataMessage

if TYPE_CHECKING:
    from pathlib import Path


class MessageReaderPort(Protocol):
    def read(
        self,
        path: Path,
    ) -> CCSDSDataMessage: ...

    def read_string(
        self,
        content: str,
    ) -> CCSDSDataMessage: ...


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
