"""
Compute backend protocols for CCSDS Orbit Data Messages.

A backend translates between OEM domain model types and the types of an
external math library (numpy, OSTk, etc.).  Each backend owns **both
directions**: domain → external and external → domain.

Guiding rules
-------------
- `from_` methods return fully constructed, Pydantic-validated domain model
  instances (concrete classes, never `Any`).
- `to_` / non-`from_` methods return `Any`; the backend decides the external
  type.
- This module imports no optional dependency (numpy, OSTk, astropy, …).
- Domain model types are imported under TYPE_CHECKING only so that this file
  has zero runtime dependencies beyond the standard library.
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
    """
    Protocol for backends that operate on OEM ephemeris (state vector) data.

    Implementations translate between OEM.Segment.EphemerisData / EphemerisDataLine
    and whatever array, trajectory, or state-vector type the backing library uses.
    """

    # ------------------------------------------------------------------
    # Decomposition: domain line → backend scalar / vector
    # ------------------------------------------------------------------

    def position(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Any:
        """Return the position vector (x, y, z) in the backend's native type."""
        ...

    def velocity(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Any:
        """Return the velocity vector (x_dot, y_dot, z_dot) in the backend's native type."""
        ...

    def acceleration(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Any:
        """
        Return the acceleration vector (x_ddot, y_ddot, z_ddot) in the backend's native
        type, or None when the line carries no acceleration components.
        """
        ...

    def parse_epoch(self, epoch: str) -> Any:
        """Parse a CCSDS §7.5.10 epoch string to the backend's epoch type."""
        ...

    # ------------------------------------------------------------------
    # domain → external
    # ------------------------------------------------------------------

    def to_array(self, data: OEM.Segment.EphemerisData) -> Any:
        """
        Convert EphemerisData to an (N, 6) or (N, 9) array in the backend's
        native type.  Accelerations are included when every line carries them.
        """
        ...

    def trajectory_from_ephemeris(self, data: OEM.Segment.EphemerisData) -> Any:
        """Build a trajectory object in the backend's native type from EphemerisData."""
        ...

    # ------------------------------------------------------------------
    # Interpolation and sampling
    # ------------------------------------------------------------------

    def interpolate(
        self,
        data: OEM.Segment.EphemerisData,
        epoch: Any,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """
        Interpolate EphemerisData at the given backend epoch and return a
        fully validated EphemerisDataLine (Pydantic validation fires).
        """
        ...

    def steps(self, start: Any, stop: Any, step: float) -> list[Any]:
        """
        Generate a sequence of backend epoch values from start to stop
        (inclusive) with the given step size in SI seconds.
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
        """
        Construct a validated EphemerisData from a (N, 6|9) array and a list
        of CCSDS epoch strings.  Pydantic validation fires on construction.
        """
        ...

    def ephemeris_data_from_trajectory(
        self,
        trajectory: Any,
    ) -> OEM.Segment.EphemerisData:
        """
        Construct a validated EphemerisData from a backend trajectory object.
        Pydantic validation fires on construction.
        """
        ...

    def state_to_line(
        self,
        state: Any,
        epoch: str,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """
        Convert a backend state object and a CCSDS epoch string to a validated
        EphemerisDataLine.  Pydantic validation fires on construction.
        """
        ...


class CovarianceBackend(Protocol):
    """
    Protocol for backends that operate on OEM covariance matrix data.

    Implementations translate between OEM.Segment.CovarianceMatrix and
    whatever array type the backing library uses.
    """

    def covariance_to_array(
        self,
        cov: OEM.Segment.CovarianceMatrix,
    ) -> Any:
        """
        Convert a CovarianceMatrix (one or more epochs) to a (N, 6, 6) array
        in the backend's native type.
        """
        ...

    def covariance_from_array(
        self,
        arr: Any,
        epochs: list[str],
        cov_ref_frame: str | None = None,
    ) -> OEM.Segment.CovarianceMatrix:
        """
        Construct a validated CovarianceMatrix from a (N, 6, 6) array, a list
        of CCSDS epoch strings, and an optional reference frame.
        Pydantic validation fires on construction.
        """
        ...
