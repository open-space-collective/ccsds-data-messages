"""
Compute backend protocols for the ``orbit_data_messages`` package.

A backend translates between OEM domain model types and the types of an
external math library (numpy, OSTk, etc.).  Each backend owns **both
directions**: domain → external and external → domain.

Note:
    ``from_`` methods return fully constructed, Pydantic-validated domain model
    instances (concrete classes, never ``Any``).  ``to_`` / non-``from_``
    methods return ``Any``; the backend decides the external type.
    This module imports no optional dependency (numpy, OSTk, astropy, …).
    Domain model types are imported under ``TYPE_CHECKING`` only so that this
    file has zero runtime dependencies beyond the standard library.
"""
from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orbit_data_messages.models.oem import OEM

    # Aliases for brevity in method signatures below.
    _EphemerisData    = OEM.Segment.EphemerisData
    _EphemerisLine    = OEM.Segment.EphemerisData.EphemerisDataLine
    _CovarianceMatrix = OEM.Segment.CovarianceMatrix


class EphemerisBackend(Protocol):
    """Protocol for backends that operate on OEM ephemeris (state-vector) data.

    Implementing classes must translate between
    ``OEM.Segment.EphemerisData`` / ``EphemerisDataLine`` and whatever array,
    trajectory, or state-vector type the backing library uses.  Both directions
    are required: domain → external (``to_`` / ``trajectory_from_ephemeris``)
    and external → domain (``from_`` methods that return validated Pydantic
    instances).
    """

    # ------------------------------------------------------------------
    # Decomposition: domain line → backend scalar / vector
    # ------------------------------------------------------------------

    def position(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Any:
        """Extract the position vector (x, y, z) from a data line.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine`` carrying position
                components in km.

        Returns:
            The position vector in the backend's native type.
        """
        ...

    def velocity(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Any:
        """Extract the velocity vector (x_dot, y_dot, z_dot) from a data line.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine`` carrying velocity
                components in km/s.

        Returns:
            The velocity vector in the backend's native type.
        """
        ...

    def acceleration(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Any:
        """Extract the acceleration vector (x_ddot, y_ddot, z_ddot) from a data line.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            The acceleration vector in the backend's native type, or ``None``
            when the line carries no acceleration components.
        """
        ...

    def parse_epoch(self, epoch: str) -> Any:
        """Parse a CCSDS §7.5.10 epoch string to the backend's epoch type.

        Direction: external → backend epoch type.

        Args:
            epoch: A CCSDS-format epoch string (e.g.
                ``"2025-01-01T00:00:00"``).

        Returns:
            The epoch in the backend's native epoch type.
        """
        ...

    # ------------------------------------------------------------------
    # domain → external
    # ------------------------------------------------------------------

    def to_array(self, data: OEM.Segment.EphemerisData) -> Any:
        """Convert ``EphemerisData`` to a dense array in the backend's native type.

        Direction: domain → external.

        Accelerations are included when every line carries them, producing an
        (N, 9) result; otherwise produces (N, 6).

        Args:
            data: A validated ``EphemerisData`` instance.

        Returns:
            An (N, 6) or (N, 9) array in the backend's native type.
        """
        ...

    def trajectory_from_ephemeris(self, data: OEM.Segment.EphemerisData) -> Any:
        """Build a trajectory object in the backend's native type from ``EphemerisData``.

        Direction: domain → external.

        Args:
            data: A validated ``EphemerisData`` instance.

        Returns:
            A trajectory object in the backend's native type.
        """
        ...

    # ------------------------------------------------------------------
    # Interpolation and sampling
    # ------------------------------------------------------------------

    def interpolate(
        self,
        data: OEM.Segment.EphemerisData,
        epoch: Any,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Interpolate ``EphemerisData`` at a given backend epoch.

        Direction: domain + external epoch → domain.

        Args:
            data: A validated ``EphemerisData`` instance.
            epoch: The target epoch in the backend's native epoch type.

        Returns:
            A fully validated ``EphemerisDataLine`` at the requested epoch.
            Pydantic validation fires on construction.
        """
        ...

    def steps(self, start: Any, stop: Any, step: float) -> list[Any]:
        """Generate a sequence of backend epoch values.

        Produces values from ``start`` to ``stop`` (inclusive) with the given
        step size in SI seconds.

        Args:
            start: Start epoch in the backend's native type.
            stop: Stop epoch in the backend's native type.
            step: Step size in seconds.

        Returns:
            A list of epoch values in the backend's native type.
        """
        ...

    # ------------------------------------------------------------------
    # external → domain  (from_ methods return validated domain instances)
    # ------------------------------------------------------------------

    def ephemeris_data_from_array(
        self,
        arr: Any,
        epochs: list[str],
    ) -> OEM.Segment.EphemerisData:
        """Construct a validated ``EphemerisData`` from a dense array and epoch strings.

        Direction: external → domain.

        Args:
            arr: An (N, 6) or (N, 9) array in the backend's native type.
                Columns are [x, y, z, x_dot, y_dot, z_dot] or with optional
                acceleration appended.
            epochs: A list of N CCSDS §7.5.10 epoch strings.

        Returns:
            A fully validated ``EphemerisData`` instance.  Pydantic validation
            fires on construction.
        """
        ...

    def ephemeris_data_from_trajectory(
        self,
        trajectory: Any,
    ) -> OEM.Segment.EphemerisData:
        """Construct a validated ``EphemerisData`` from a backend trajectory object.

        Direction: external → domain.

        Args:
            trajectory: A trajectory object in the backend's native type.

        Returns:
            A fully validated ``EphemerisData`` instance.  Pydantic validation
            fires on construction.
        """
        ...

    def state_to_line(
        self,
        state: Any,
        epoch: str,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Convert a backend state object and a CCSDS epoch string to a data line.

        Direction: external → domain.

        Args:
            state: A state object in the backend's native type.
            epoch: A CCSDS §7.5.10 epoch string.

        Returns:
            A fully validated ``EphemerisDataLine``.  Pydantic validation fires
            on construction.
        """
        ...


class CovarianceBackend(Protocol):
    """Protocol for backends that operate on OEM covariance matrix data.

    Implementing classes must translate between
    ``OEM.Segment.CovarianceMatrix`` and whatever array type the backing
    library uses.  Both directions are required: domain → external
    (``covariance_to_array``) and external → domain
    (``covariance_from_array``), with ``covariance_from_array`` returning a
    fully validated Pydantic instance.
    """

    def covariance_to_array(
        self,
        cov: OEM.Segment.CovarianceMatrix,
    ) -> Any:
        """Convert a ``CovarianceMatrix`` to a dense array in the backend's native type.

        Direction: domain → external.

        Args:
            cov: A validated ``CovarianceMatrix`` instance covering one or more
                epochs.

        Returns:
            An (N, 6, 6) array in the backend's native type, where each slice
            is the symmetric 6×6 covariance matrix reconstructed from the 21
            lower-triangular elements.
        """
        ...

    def covariance_from_array(
        self,
        arr: Any,
        epochs: list[str],
        cov_ref_frame: str | None = None,
    ) -> OEM.Segment.CovarianceMatrix:
        """Construct a validated ``CovarianceMatrix`` from a dense array and epoch strings.

        Direction: external → domain.

        Args:
            arr: An (N, 6, 6) array in the backend's native type.
            epochs: A list of N CCSDS §7.5.10 epoch strings.
            cov_ref_frame: Optional reference frame string.  When ``None``, no
                ``COV_REF_FRAME`` keyword is set on the resulting lines.

        Returns:
            A fully validated ``CovarianceMatrix`` instance.  Pydantic
            validation fires on construction.
        """
        ...
