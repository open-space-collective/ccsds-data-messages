"""
KVN adapter: Orbit Parameter Message writer.

OPM KVN is completely flat — no *_START/*_STOP block delimiters of any kind
(spec Annex G, figures G-1 through G-4).  Keyword names come from FieldMetadata
annotations on the domain model; nothing is hardcoded in this adapter.

Keyword order follows the spec tables (§3.2.2 table 3-1, §3.2.3 table 3-2,
§3.2.4 table 3-3).  Pydantic preserves field declaration order in model_fields,
which matches the spec table order.

Optional fields are omitted when None (§6.2.1.4 equivalent for OPM: optional
KVN assignments may be omitted).

Spec references: §3.2 (OPM structure), §7.3–7.4 (KVN rules), §7.8.7 (comments).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import emit_block
from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.models.opm import OPM


class KVNOPMWriter:
    """
    Writes a validated OPM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OPM, path: Path, *, options: WriterOptions | None = None) -> None:
        """Serializes a validated OPM domain model to a KVN file at path.

        Args:
            message: Validated OPM instance to serialize.
            path: Destination file. Created or overwritten.
            options: Formatting options. When omitted, WriterOptions() defaults apply.
        """
        with path.open("w", encoding="utf-8") as out:
            # Header (table 3-1) — flat, no delimiters.
            emit_block(message.header, out, options=options)
            out.write("\n")

            # Metadata (table 3-2) — flat, no delimiters per spec Annex G.
            emit_block(message.metadata, out, options=options)
            out.write("\n")

            # State vector (table 3-3, §3.2.4) — mandatory.
            emit_block(message.data.state_vector, out, options=options)
            out.write("\n")

            # Osculating Keplerian elements (table 3-3) — optional, all-or-none.
            if message.data.osculating_keplerian_elements is not None:
                emit_block(message.data.osculating_keplerian_elements, out, options=options)
                out.write("\n")

            # Spacecraft parameters (table 3-3) — optional.
            if message.data.spacecraft_parameters is not None:
                emit_block(message.data.spacecraft_parameters, out, options=options)
                out.write("\n")

            # Covariance matrix (table 3-3, §3.2.4.10) — flat KVs, no
            # COVARIANCE_START/STOP block (OPM format is entirely flat).
            if message.data.covariance_matrix is not None:
                emit_block(message.data.covariance_matrix, out, options=options)
                out.write("\n")

            # Maneuver parameters (table 3-3, §3.2.4.8) — repeated per maneuver.
            if message.data.maneuvers:
                for maneuver in message.data.maneuvers:
                    emit_block(maneuver, out, options=options)
                    out.write("\n")

            # User-defined parameters (table 3-3, §3.2.4.12) — optional.
            if message.data.user_defined is not None:
                emit_block(message.data.user_defined, out, options=options)


OrbitParameterMessageKVNWriter = KVNOPMWriter
