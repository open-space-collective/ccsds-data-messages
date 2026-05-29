"""
Compute views for CCSDS Orbit Data Messages.

A view binds a domain model to a backend.  It is a lightweight wrapper:
it owns no data, copies nothing, and leaves the domain model unchanged.

Three views are provided:

    EphemerisView(data, backend)
        Iterable over StateView instances (one per ephemeris line).
        Callable: view(epoch) → interpolated EphemerisDataLine.
        Shortcuts: to_numpy(), to_ostk() — deferred backend import.

    StateView(line, backend)
        Properties epoch, position, velocity, acceleration — all delegated
        to the backend; no computation lives in the view itself.

    CovarianceView(cov, backend)
        Iterable over backend-native 6×6 matrices (one per epoch).
        Shortcut: to_numpy() — deferred backend import.

Removing to_numpy() / to_ostk() entirely leaves every view fully functional.
No backend is imported at module load time.
"""
from __future__ import annotations

from typing import Any
from typing import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orbit_data_messages.compute.backends.base import CovarianceBackend
    from orbit_data_messages.compute.backends.base import EphemerisBackend
    from orbit_data_messages.models.oem import OEM


# ---------------------------------------------------------------------------
# StateView
# ---------------------------------------------------------------------------

class StateView:
    """A single ephemeris state line bound to a backend.

    All properties delegate to the backend — the view contains no computation.
    This view holds a reference to the domain model — it does not copy data.
    """

    __slots__ = ("_line", "_backend")

    def __init__(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
        backend: EphemerisBackend,
    ) -> None:
        self._line    = line
        self._backend = backend

    @property
    def epoch(self) -> str:
        """CCSDS §7.5.10 epoch string read directly from the domain model."""
        return self._line.epoch

    @property
    def position(self) -> Any:
        """Position vector delegated to the backend's native type."""
        return self._backend.position(self._line)

    @property
    def velocity(self) -> Any:
        """Velocity vector delegated to the backend's native type."""
        return self._backend.velocity(self._line)

    @property
    def acceleration(self) -> Any:
        """Acceleration vector delegated to the backend, or None if absent."""
        return self._backend.acceleration(self._line)

    @property
    def line(self) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Read-only reference to the underlying domain model EphemerisDataLine."""
        return self._line

    def __repr__(self) -> str:
        return f"StateView(epoch={self._line.epoch!r})"


# ---------------------------------------------------------------------------
# EphemerisView
# ---------------------------------------------------------------------------

class EphemerisView:
    """An EphemerisData block bound to a backend.

    Iterable — yields one StateView per data line.
    Callable  — delegates interpolation to ``backend.interpolate(data, epoch)``.
    Shortcuts — ``to_numpy()`` and ``to_ostk()`` use deferred backend imports.
    This view holds a reference to the domain model — it does not copy data.
    """

    __slots__ = ("_data", "_backend")

    def __init__(
        self,
        data: OEM.Segment.EphemerisData,
        backend: EphemerisBackend,
    ) -> None:
        self._data    = data
        self._backend = backend

    # ------------------------------------------------------------------
    # Core interface (fully functional without to_numpy / to_ostk)
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[StateView]:
        """Yield one StateView per ephemeris data line, in document order."""
        for line in self._data.ephemeris_data_lines:
            yield StateView(line, self._backend)

    def __len__(self) -> int:
        return len(self._data.ephemeris_data_lines)

    def __call__(self, epoch: Any) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Interpolate the ephemeris at the given epoch by delegating to the backend.

        Delegates to ``backend.interpolate(data, epoch)``. All interpolation
        logic lives in the backend — the view contains none.

        Args:
            epoch: The target epoch in the backend's native type (e.g. the
                output of ``backend.parse_epoch()``).

        Returns:
            A validated EphemerisDataLine at the requested epoch.
        """
        return self._backend.interpolate(self._data, epoch)

    @property
    def data(self) -> OEM.Segment.EphemerisData:
        """Read-only reference to the underlying domain model EphemerisData."""
        return self._data

    @property
    def backend(self) -> EphemerisBackend:
        """The backend bound to this view."""
        return self._backend

    # ------------------------------------------------------------------
    # Convenience shortcuts — deferred backend imports (not at module level)
    # ------------------------------------------------------------------

    def to_numpy(self) -> Any:
        """Return a (N, 6) or (N, 9) numpy array.

        Convenience wrapper that delegates to ``NumpyBackend().to_array()``.
        The import of ``NumpyBackend`` is deferred to this method body so that
        the view module never loads numpy at import time.

        Returns:
            An ``ndarray`` of shape ``(N, 6)`` when no accelerations are
            present, or ``(N, 9)`` when accelerations are present.

        Raises:
            ImportError: If numpy is not installed. Install with
                ``pip install orbit-data-messages[numpy]``.
        """
        from orbit_data_messages.compute.backends.numpy_ import NumpyBackend  # deferred
        return NumpyBackend().to_array(self._data)

    def to_ostk(self) -> Any:
        """Return an OSTk Trajectory object.

        Convenience wrapper that delegates to
        ``OSTkBackend().trajectory_from_ephemeris()``. The import of
        ``OSTkBackend`` is deferred to this method body so that the view
        module never loads OSTk at import time.

        Returns:
            An OSTk ``Trajectory`` built from this ephemeris data.

        Raises:
            ImportError: If OSTk is not installed. Install with
                ``pip install orbit-data-messages[ostk]``.
        """
        from orbit_data_messages.compute.backends.ostk_ import OSTkBackend   # deferred
        return OSTkBackend().trajectory_from_ephemeris(self._data)

    def __repr__(self) -> str:
        return (
            f"EphemerisView("
            f"n={len(self)}, "
            f"backend={type(self._backend).__name__})"
        )


# ---------------------------------------------------------------------------
# CovarianceView
# ---------------------------------------------------------------------------

class CovarianceView:
    """A CovarianceMatrix block bound to a backend.

    Iterable — yields one backend-native 6×6 matrix per epoch.
    Shortcut  — ``to_numpy()`` uses a deferred ``NumpyBackend`` import.
    This view holds a reference to the domain model — it does not copy data.
    """

    __slots__ = ("_cov", "_backend")

    def __init__(
        self,
        cov: OEM.Segment.CovarianceMatrix,
        backend: CovarianceBackend,
    ) -> None:
        self._cov     = cov
        self._backend = backend

    # ------------------------------------------------------------------
    # Core interface (fully functional without to_numpy)
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[Any]:
        """Yield one backend-native 6×6 matrix per covariance epoch, in order."""
        for matrix in self._backend.covariance_to_array(self._cov):
            yield matrix

    def __len__(self) -> int:
        return len(self._cov.covariance_matrix_lines)

    @property
    def cov(self) -> OEM.Segment.CovarianceMatrix:
        """Read-only reference to the underlying domain model CovarianceMatrix."""
        return self._cov

    @property
    def backend(self) -> CovarianceBackend:
        """The backend bound to this view."""
        return self._backend

    # ------------------------------------------------------------------
    # Convenience shortcut — deferred backend import
    # ------------------------------------------------------------------

    def to_numpy(self) -> Any:
        """Return a (N, 6, 6) numpy array.

        Convenience wrapper that delegates to
        ``NumpyBackend().covariance_to_array()``. The import of
        ``NumpyBackend`` is deferred to this method body so that the view
        module never loads numpy at import time.

        Returns:
            An ``ndarray`` of shape ``(N, 6, 6)``.

        Raises:
            ImportError: If numpy is not installed. Install with
                ``pip install orbit-data-messages[numpy]``.
        """
        from orbit_data_messages.compute.backends.numpy_ import NumpyBackend  # deferred
        return NumpyBackend().covariance_to_array(self._cov)

    def __repr__(self) -> str:
        return (
            f"CovarianceView("
            f"n={len(self)}, "
            f"backend={type(self._backend).__name__})"
        )
