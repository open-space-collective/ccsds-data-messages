"""
KVN adapter: Orbit Mean-Elements Message writer.

OMM KVN is completely flat: no *_START/*_STOP block delimiters (spec Annex G,
figures G-7 and G-8). Keyword order follows spec tables 4-1, 4-2, 4-3.
Maneuvers are not accommodated in the OMM (section 4.2.4.8).

Spec references: sections 4.2, 7.3-7.4, 7.8.8.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from ccsds_data_messages.io.kvn._utils import (
    SupportsWrite,
    emit_block,
    emit_user_defined,
    guard_lines,
)
from ccsds_data_messages.io.kvn.parser import ODM_MAX_LINE_LENGTH
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models.omm import OMM

if TYPE_CHECKING:
    from pathlib import Path


class KVNOMMWriter:
    """
    Write a validated OMM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def _write(
        self, message: OMM, out: SupportsWrite, *, options: WriterOptions | None = None
    ) -> None:
        out = guard_lines(out, max_line_length=ODM_MAX_LINE_LENGTH)
        emit_block(message.header, out, options=options)
        out.write("\n")

        emit_block(message.metadata, out, options=options)
        out.write("\n")

        emit_block(message.data.mean_keplerian_elements, out, options=options)
        out.write("\n")

        if message.data.spacecraft_parameters is not None:
            emit_block(message.data.spacecraft_parameters, out, options=options)
            out.write("\n")

        if message.data.tle_related_parameters is not None:
            emit_block(message.data.tle_related_parameters, out, options=options)
            out.write("\n")

        if message.data.covariance_matrix is not None:
            emit_block(message.data.covariance_matrix, out, options=options)
            out.write("\n")

        if message.data.user_defined is not None:
            emit_user_defined(message.data.user_defined.user_defined, out)

    def write(
        self, message: OMM, path: Path, *, options: WriterOptions | None = None
    ) -> None:
        with path.open("w", encoding="utf-8") as out:
            self._write(message, out, options=options)

    def write_string(self, message: OMM, *, options: WriterOptions | None = None) -> str:
        with io.StringIO() as buffer:
            self._write(message, buffer, options=options)
            return buffer.getvalue()


OrbitMeanElementsMessageKVNWriter = KVNOMMWriter
