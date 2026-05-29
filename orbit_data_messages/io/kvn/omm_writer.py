"""
KVN adapter: Orbit Mean-Elements Message writer.

OMM KVN is completely flat — no *_START/*_STOP block delimiters (spec Annex G,
figures G-7 and G-8).  Keyword names come from FieldMetadata annotations on the
domain model.  Field order follows table 4-3 (preserved via model_fields order).

Maneuvers are not accommodated in the OMM (§4.2.4.8).

Spec references: §4.2 (OMM structure), §7.3–7.4 (KVN rules), §7.8.8 (comments).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import emit_block
from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.models.omm import OMM


class KVNOMMWriter:
    """
    Writes a validated OMM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OMM, path: Path, *, options: WriterOptions | None = None) -> None:
        """Serializes a validated OMM domain model to a KVN file at path.

        Args:
            message: Validated OMM instance to serialize.
            path: Destination file. Created or overwritten.
            options: Formatting options. When omitted, WriterOptions() defaults apply.
        """
        with path.open("w", encoding="utf-8") as out:
            # Header (table 4-1) — flat, no delimiters.
            emit_block(message.header, out, options=options)
            out.write("\n")

            # Metadata (table 4-2) — flat, no delimiters.
            emit_block(message.metadata, out, options=options)
            out.write("\n")

            # Mean Keplerian elements (table 4-3, §4.2.4) — mandatory.
            emit_block(message.data.mean_keplerian_elements, out, options=options)
            out.write("\n")

            # Spacecraft parameters (table 4-3) — optional.
            if message.data.spacecraft_parameters is not None:
                emit_block(message.data.spacecraft_parameters, out, options=options)
                out.write("\n")

            # TLE related parameters (table 4-3, §4.2.4.6) — conditional.
            if message.data.tle_related_parameters is not None:
                emit_block(message.data.tle_related_parameters, out, options=options)
                out.write("\n")

            # Covariance matrix (table 4-3, §4.2.4.5) — flat KVs, no block
            # delimiters (OMM format is entirely flat, same as OPM).
            if message.data.covariance_matrix is not None:
                emit_block(message.data.covariance_matrix, out, options=options)
                out.write("\n")

            # User-defined parameters (table 4-3, §4.2.4.10) — optional.
            if message.data.user_defined is not None:
                emit_block(message.data.user_defined, out, options=options)


OrbitMeanElementsMessageKVNWriter = KVNOMMWriter
