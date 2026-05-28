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
from orbit_data_messages.models.ocm import OCM


class KVNOCMWriter:
    """
    Writes a validated OCM domain model to a KVN-format file.

    Satisfies MessageWriterPort structurally.
    """

    def write(self, message: OCM, path: Path) -> None:
        with path.open("w", encoding="utf-8") as out:
            # Header (table 6-2) — flat, no block delimiters.
            emit_block(message.header, out)
            out.write("\n")

            # Metadata (table 6-3).
            # Delineation("META_START", "META_STOP") on OCM.Metadata.
            emit_block(message.metadata, out)
            out.write("\n")

            # Trajectory state blocks (table 6-4, §6.2.5) — repeatable.
            # Delineation("TRAJ_START", "TRAJ_STOP") on TrajectoryStateBlock.
            # data_lines (§7.4.1.5) written after the KV metadata.
            if message.trajectory_states:
                for block in message.trajectory_states:
                    emit_block(block, out, extra_lines=block.data_lines)
                    out.write("\n")

            # Physical properties block (table 6-5, §6.2.6) — at most one.
            # Delineation("PHYS_START", "PHYS_STOP") on PhysicalPropertiesBlock.
            if message.physical_properties is not None:
                emit_block(message.physical_properties, out)
                out.write("\n")

            # Covariance blocks (table 6-6, §6.2.7) — repeatable.
            # Delineation("COV_START", "COV_STOP") on CovarianceBlock.
            # data_lines (§7.4.1.6) written after the KV metadata.
            if message.covariances:
                for block in message.covariances:
                    emit_block(block, out, extra_lines=block.data_lines)
                    out.write("\n")

            # Maneuver blocks (table 6-7, §6.2.8) — repeatable.
            # Delineation("MAN_START", "MAN_STOP") on ManeuverBlock.
            # data_lines (§7.4.1.7) written after the KV metadata.
            if message.maneuvers:
                for block in message.maneuvers:
                    emit_block(block, out, extra_lines=block.data_lines)
                    out.write("\n")

            # Perturbations block (table 6-10, §6.2.9) — at most one.
            # Delineation("PERT_START", "PERT_STOP") on PerturbationsBlock.
            if message.perturbations is not None:
                emit_block(message.perturbations, out)
                out.write("\n")

            # Orbit determination block (table 6-11, §6.2.10) — at most one.
            # Delineation("OD_START", "OD_STOP") on OrbitDeterminationBlock.
            if message.orbit_determination is not None:
                emit_block(message.orbit_determination, out)
                out.write("\n")

            # User-defined parameters block (table 6-12, §6.2.11) — at most one.
            # Delineation("USER_START", "USER_STOP") on UserDefinedParameters.
            if message.user_defined is not None:
                emit_block(message.user_defined, out)


OrbitComprehensiveMessageKVNWriter = KVNOCMWriter
