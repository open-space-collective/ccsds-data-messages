"""
KVN adapter: Orbit Comprehensive Message writer.

All block delimiter names (META_START/STOP, TRAJ_START/STOP, etc.) come from
the Delineation private attributes on the domain model classes — nothing is
hardcoded in this adapter.  Keyword names come from FieldMetadata annotations.

OCM block order per §6.2.1.1 (table 6-1):
  Header, Metadata, [Trajectory blocks]*, [Physical properties],
  [Covariance blocks]*, [Maneuver blocks]*, [Perturbations],
  [Orbit determination], [User-defined]

Trajectory, covariance, and maneuver blocks are repeatable (§6.2.5.3,
§6.2.7.3, §6.2.8.x).

Data lines within TRAJ/COV/MAN blocks (§7.4.1.5–7.4.1.7):
  These are raw strings stored in data_lines; written verbatim after the KV
  metadata for that block.

Spec references: §6.2 (OCM structure), §7.3–7.4 (KVN rules), §7.8.10 (comments).
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.kvn._utils import emit_block
from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.models.ocm import OCM


class KVNOCMWriter:
    """
    Writes a validated OCM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OCM, path: Path, *, options: WriterOptions | None = None) -> None:
        """Serializes a validated OCM domain model to a KVN file at path.

        Args:
            message: Validated OCM instance to serialize.
            path: Destination file. Created or overwritten.
            options: Formatting options. When omitted, WriterOptions() defaults apply.
        """
        with path.open("w", encoding="utf-8") as out:
            emit_block(message.header, out, options=options)
            out.write("\n")

            emit_block(message.metadata, out, options=options)
            out.write("\n")

            if message.trajectory_states:
                for block in message.trajectory_states:
                    emit_block(block, out, extra_lines=block.data_lines, options=options)
                    out.write("\n")

            if message.physical_properties is not None:
                emit_block(message.physical_properties, out, options=options)
                out.write("\n")

            if message.covariances:
                for block in message.covariances:
                    emit_block(block, out, extra_lines=block.data_lines, options=options)
                    out.write("\n")

            if message.maneuvers:
                for block in message.maneuvers:
                    emit_block(block, out, extra_lines=block.data_lines, options=options)
                    out.write("\n")

            if message.perturbations is not None:
                emit_block(message.perturbations, out, options=options)
                out.write("\n")

            if message.orbit_determination is not None:
                emit_block(message.orbit_determination, out, options=options)
                out.write("\n")

            if message.user_defined is not None:
                emit_block(message.user_defined, out, options=options)


OrbitComprehensiveMessageKVNWriter = KVNOCMWriter
