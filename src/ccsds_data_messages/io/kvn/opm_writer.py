"""
KVN adapter: Orbit Parameter Message writer.

OPM KVN is completely flat: no *_START/*_STOP block delimiters (spec Annex G,
figures G-1 through G-4). Keyword order follows spec tables 3-1, 3-2, 3-3.
Optional fields are omitted when None.

Spec references: sections 3.2, 7.3-7.4, 7.8.7.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from ccsds_data_messages.io.kvn._utils import SupportsWrite
from ccsds_data_messages.io.kvn._utils import emit_block
from ccsds_data_messages.io.kvn._utils import guard_lines
from ccsds_data_messages.io.kvn.parser import ODM_MAX_LINE_LENGTH
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models.opm import OPM

if TYPE_CHECKING:
    from pathlib import Path


class KVNOPMWriter:
    """
    Writes a validated OPM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def _write(
        self, message: OPM, out: SupportsWrite, *, options: WriterOptions | None = None
    ) -> None:
        out = guard_lines(out, max_line_length=ODM_MAX_LINE_LENGTH)
        emit_block(message.header, out, options=options)
        out.write("\n")

        emit_block(message.metadata, out, options=options)
        out.write("\n")

        emit_block(message.data.state_vector, out, options=options)
        out.write("\n")

        if message.data.osculating_keplerian_elements is not None:
            emit_block(message.data.osculating_keplerian_elements, out, options=options)
            out.write("\n")

        if message.data.spacecraft_parameters is not None:
            emit_block(message.data.spacecraft_parameters, out, options=options)
            out.write("\n")

        if message.data.covariance_matrix is not None:
            emit_block(message.data.covariance_matrix, out, options=options)
            out.write("\n")

        if message.data.maneuvers:
            for maneuver in message.data.maneuvers:
                emit_block(maneuver, out, options=options)
                out.write("\n")

        if message.data.user_defined is not None:
            emit_block(message.data.user_defined, out, options=options)

    def write(
        self, message: OPM, path: Path, *, options: WriterOptions | None = None
    ) -> None:
        with path.open("w", encoding="utf-8") as out:
            self._write(message, out, options=options)

    def write_string(self, message: OPM, *, options: WriterOptions | None = None) -> str:
        with io.StringIO() as buffer:
            self._write(message, buffer, options=options)
            return buffer.getvalue()


OrbitParameterMessageKVNWriter = KVNOPMWriter
