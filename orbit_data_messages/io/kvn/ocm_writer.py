"""
All block delimiter names (META_START/STOP, TRAJ_START/STOP, etc.) come from
the ``Delineation`` private attributes on the domain model classes: nothing is
hardcoded.  Keyword names come from FieldMetadata annotations.

OCM block order per section 6.2.1.1 (table 6-1):
- Header,
- Metadata,
- [Trajectory states]*,
- [Physical characteristics],
- [Covariance blocks]*,
- [Maneuver blocks]*,
- [Perturbations],
- [Orbit determination],
- [User-defined parameters]

Spec references:
- Section 6.2 (OCM structure)
- Section 7.3-7.4 (KVN rules)
- Section 7.8.10 (comments)
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

from orbit_data_messages.io.kvn._utils import emit_block
from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.models.ocm import OCM


class KVNOCMWriter:
    """
    Write a validated OCM domain model to a KVN-format file.

    Satisfies ``MessageWriterPort`` structurally.
    """

    def _write(
        self,
        message: OCM,
        out: TextIO,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serialize a validated OCM domain model to a KVN file.

        Args:
            message (OCM): Validated OCM instance to serialize.
            out (TextIO): Destination text stream.
            options (WriterOptions | None): Formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        # Header (table 6-1): flat, no delimiters.
        emit_block(message.header, out, options=options)
        out.write("\n")

        # Metadata (table 6-3, section 6.2.4): delimited by META_START/META_STOP.
        emit_block(message.metadata, out, options=options)
        out.write("\n")

        # Trajectory state blocks (table 6-4, section 6.2.5): optional, repeatable.
        if message.trajectory_states:
            for block in message.trajectory_states:
                emit_block(block, out, extra_lines=block.data_lines, options=options)
                out.write("\n")

        # Physical characteristics (table 6-5, section 6.2.6): optional, at most one.
        if message.physical_characteristics is not None:
            emit_block(message.physical_characteristics, out, options=options)
            out.write("\n")

        # Covariance blocks (table 6-6, section 6.2.7.3): optional, repeatable.
        if message.covariances:
            for block in message.covariances:
                emit_block(block, out, extra_lines=block.data_lines, options=options)
                out.write("\n")

        # Maneuver blocks (table 6-7, section 6.2.8.4): optional, repeatable.
        if message.maneuvers:
            for block in message.maneuvers:
                emit_block(block, out, extra_lines=block.data_lines, options=options)
                out.write("\n")

        # Perturbations (table 6-10, section 6.2.9.2): conditional, at most one.
        if message.perturbations is not None:
            emit_block(message.perturbations, out, options=options)
            out.write("\n")

        # Orbit determination (table 6-11, section 6.2.10.5): optional, at most one.
        if message.orbit_determination is not None:
            emit_block(message.orbit_determination, out, options=options)
            out.write("\n")

        # User-defined parameters (table 6-12, section 6.2.11.2): optional, at most one.
        if message.user_defined is not None:
            emit_block(message.user_defined, out, options=options)

    def write(
        self,
        message: OCM,
        path: Path,
        *,
        options: WriterOptions | None = None,
    ) -> None:
        """
        Serialize a validated OCM domain model to a KVN file at ``path``.

        Args:
            message (OCM): Validated OCM instance to serialize.
            path (Path): Destination file. Created or overwritten.
            options (WriterOptions | None): Formatting options. When omitted, ``WriterOptions()`` defaults apply.
        """
        with path.open("w", encoding="utf-8") as out:
            self._write(message, out, options=options)

    def write_string(
        self, message: OCM, *, options: WriterOptions | None = None,
    ) -> str:
        """
        Serialize a validated OCM domain model to a KVN string.

        Args:
            message (OCM): Validated OCM instance to serialize.
            options (WriterOptions | None): Formatting options. When omitted, ``WriterOptions()`` defaults apply.

        Returns:
            str: The serialized content.
        """
        with io.StringIO() as buffer:
            self._write(message, buffer, options=options)
            return buffer.getvalue()


OrbitComprehensiveMessageKVNWriter = KVNOCMWriter
