"""
NumPy compute backend for the ``orbit_data_messages`` package.

Satisfies ``EphemerisBackend`` and ``CovarianceBackend`` protocols.
Requires ``numpy``.

The numpy import is guarded at module top: importing this module raises
``ImportError`` with install instructions if numpy is not available.

Fully implemented:
    position, velocity, acceleration, parse_epoch, to_array, steps,
    state_to_line, ephemeris_data_from_array,
    covariance_to_array, covariance_from_array.

Raises NotImplementedError:
    trajectory_from_ephemeris, interpolate, ephemeris_data_from_trajectory
    (these require an interpolation library or OSTk; use ``OSTkBackend``
    instead).
"""
from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

try:
    import numpy as np
except ImportError as _err:
    raise ImportError(
        "NumpyBackend requires numpy. "
        "Install it with:  pip install orbit-data-messages[numpy]"
    ) from _err

if TYPE_CHECKING:
    from orbit_data_messages.models.oem import OEM

# ---------------------------------------------------------------------------
# Covariance LTM field order — derived from the domain model at import time,
# not hardcoded.  This mirrors the approach in the KVN OEM reader.
# ---------------------------------------------------------------------------

def _build_cov_layout() -> tuple[list[str], list[tuple[int, int]]]:
    """Build the covariance lower-triangular-matrix field list and position map.

    Derives field names from ``CovarianceMatrixLines.model_fields`` at import
    time so the layout stays in sync with the domain model automatically.

    Returns:
        A tuple ``(field_names, positions)`` where ``field_names`` is the
        ordered list of the 21 LTM field names and ``positions`` is the
        corresponding list of ``(row, col)`` 0-indexed positions in a 6×6
        lower-triangular matrix.
    """
    from orbit_data_messages.models.oem import OEM as _OEM
    _CML = _OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
    fields = [fn for fn in _CML.model_fields if fn not in ("epoch", "cov_ref_frame")]
    # LTM positions: row i contains i+1 elements (0-indexed, lower triangular).
    positions: list[tuple[int, int]] = []
    r, c = 0, 0
    for _ in fields:
        positions.append((r, c))
        c += 1
        if c > r:
            r += 1
            c = 0
    return fields, positions


_COV_FIELDS, _COV_POSITIONS = _build_cov_layout()


# ---------------------------------------------------------------------------
# Epoch helpers
# ---------------------------------------------------------------------------

def _to_datetime64(epoch: str) -> np.datetime64:
    """Convert a CCSDS epoch string to ``np.datetime64``.

    Args:
        epoch: A CCSDS §7.5.10 epoch string, optionally trailing ``Z``.

    Returns:
        A ``np.datetime64`` value with microsecond precision.
    """
    return np.datetime64(epoch.rstrip("Z"))


def _from_datetime64(dt64: np.datetime64) -> str:
    """Convert a ``np.datetime64`` to a CCSDS epoch string.

    Normalizes to microsecond precision, then strips trailing zeros from the
    fractional-seconds part.

    Args:
        dt64: A ``np.datetime64`` value.

    Returns:
        A CCSDS-format epoch string without trailing ``Z``.
    """
    # Normalize to microsecond precision then format.
    epoch_str = str(np.datetime64(dt64, "us"))
    # np formats as '2025-01-01T00:00:00.000000' — strip trailing zeros.
    if "." in epoch_str:
        epoch_str = epoch_str.rstrip("0").rstrip(".")
    return epoch_str


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

class NumpyBackend:
    """Compute backend using numpy.

    Satisfies ``EphemerisBackend`` and ``CovarianceBackend`` protocols.
    Requires ``numpy``.
    """

    # ------------------------------------------------------------------
    # EphemerisBackend — decomposition
    # ------------------------------------------------------------------

    def position(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> np.ndarray:
        """Return the position vector as a numpy array.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            A ``(3,)`` float64 array ``[x, y, z]`` in km.
        """
        return np.array([line.x, line.y, line.z], dtype=np.float64)

    def velocity(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> np.ndarray:
        """Return the velocity vector as a numpy array.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            A ``(3,)`` float64 array ``[x_dot, y_dot, z_dot]`` in km/s.
        """
        return np.array([line.x_dot, line.y_dot, line.z_dot], dtype=np.float64)

    def acceleration(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> np.ndarray | None:
        """Return the acceleration vector as a numpy array, or ``None``.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            A ``(3,)`` float64 array ``[x_ddot, y_ddot, z_ddot]`` in km/s²,
            or ``None`` when no acceleration is present.
        """
        if line.x_ddot is None:
            return None
        return np.array([line.x_ddot, line.y_ddot, line.z_ddot], dtype=np.float64)

    def parse_epoch(self, epoch: str) -> np.datetime64:
        """Parse a CCSDS §7.5.10 epoch string to ``np.datetime64``.

        Direction: external string → numpy epoch type.

        Args:
            epoch: A CCSDS-format epoch string.

        Returns:
            A ``np.datetime64`` value with microsecond precision.
        """
        return _to_datetime64(epoch)

    # ------------------------------------------------------------------
    # EphemerisBackend — domain → external
    # ------------------------------------------------------------------

    def to_array(self, data: OEM.Segment.EphemerisData) -> np.ndarray:
        """Convert ``EphemerisData`` to a float64 numpy array.

        Direction: domain → external.

        Shape is ``(N, 6)`` when no line carries acceleration components;
        ``(N, 9)`` when every line carries them.  The shape is determined
        per-segment from the actual data, not assumed.

        Args:
            data: A validated ``EphemerisData`` instance.

        Returns:
            A float64 numpy array of shape ``(N, 6)`` or ``(N, 9)``.
        """
        lines = data.ephemeris_data_lines
        has_accel = all(line.x_ddot is not None for line in lines)
        cols = 9 if has_accel else 6

        arr = np.empty((len(lines), cols), dtype=np.float64)
        for i, line in enumerate(lines):
            arr[i, 0] = line.x
            arr[i, 1] = line.y
            arr[i, 2] = line.z
            arr[i, 3] = line.x_dot
            arr[i, 4] = line.y_dot
            arr[i, 5] = line.z_dot
            if has_accel:
                arr[i, 6] = line.x_ddot  # type: ignore[assignment]
                arr[i, 7] = line.y_ddot  # type: ignore[assignment]
                arr[i, 8] = line.z_ddot  # type: ignore[assignment]
        return arr

    def trajectory_from_ephemeris(
        self,
        data: OEM.Segment.EphemerisData,
    ) -> Any:
        """Raise ``NotImplementedError``; trajectory construction requires OSTk.

        Direction: domain → external (not implemented).

        Args:
            data: A validated ``EphemerisData`` instance.

        Raises:
            NotImplementedError: Always.  Install the ``ostk`` extra
                (``pip install orbit-data-messages[ostk]``) and use
                ``OSTkBackend``.
        """
        raise NotImplementedError(
            "trajectory_from_ephemeris requires OSTk. "
            "Install the 'ostk' extra and use OSTkBackend."
        )

    # ------------------------------------------------------------------
    # EphemerisBackend — interpolation and sampling
    # ------------------------------------------------------------------

    def interpolate(
        self,
        data: OEM.Segment.EphemerisData,
        epoch: Any,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Raise ``NotImplementedError``; interpolation is not yet implemented.

        Direction: domain + external epoch → domain (not implemented).

        Args:
            data: A validated ``EphemerisData`` instance.
            epoch: The target epoch.

        Raises:
            NotImplementedError: Always.  Use ``OSTkBackend`` for
                Hermite/Lagrange interpolation.
        """
        raise NotImplementedError(
            "NumpyBackend does not yet implement interpolation. "
            "Use OSTkBackend for Hermite/Lagrange interpolation."
        )

    def steps(
        self,
        start: np.datetime64,
        stop: np.datetime64,
        step: float,
    ) -> list[np.datetime64]:
        """Generate ``np.datetime64`` epoch values from ``start`` to ``stop``.

        ``start`` and ``stop`` must be ``np.datetime64`` as returned by
        ``parse_epoch``.

        Args:
            start: Start epoch as ``np.datetime64``.
            stop: Stop epoch as ``np.datetime64`` (inclusive).
            step: Step size in seconds.

        Returns:
            A list of ``np.datetime64`` values covering the interval.
        """
        step_us = np.timedelta64(round(step * 1_000_000), "us")
        result: list[np.datetime64] = []
        current = np.datetime64(start, "us")
        stop_us = np.datetime64(stop, "us")
        while current <= stop_us:
            result.append(current)
            current = current + step_us
        return result

    # ------------------------------------------------------------------
    # EphemerisBackend — external → domain  (from_ methods)
    # ------------------------------------------------------------------

    def ephemeris_data_from_array(
        self,
        arr: np.ndarray,
        epochs: list[str],
    ) -> OEM.Segment.EphemerisData:
        """Construct a validated ``EphemerisData`` from a float64 array and epoch strings.

        Direction: external → domain.

        Numpy scalars are explicitly converted to Python ``float`` before being
        passed to the domain model, so Pydantic receives plain Python types.

        Args:
            arr: A float64 numpy array of shape ``(N, 6)`` or ``(N, 9)``.
                Columns are ``[x, y, z, x_dot, y_dot, z_dot]`` with optional
                acceleration appended.
            epochs: A list of N CCSDS §7.5.10 epoch strings.

        Returns:
            A fully validated ``EphemerisData`` instance.  Pydantic validation
            fires on construction.

        Raises:
            ValueError: If the number of rows does not match ``len(epochs)``,
                or if ``arr`` does not have 6 or 9 columns.
        """
        from orbit_data_messages.models.oem import OEM as _OEM  # lazy import

        arr = np.asarray(arr, dtype=np.float64)
        n, cols = arr.shape
        if n != len(epochs):
            raise ValueError(
                f"arr has {n} rows but {len(epochs)} epochs were supplied."
            )
        if cols not in (6, 9):
            raise ValueError(f"arr must have 6 or 9 columns; got {cols}.")

        lines = []
        for i, epoch in enumerate(epochs):
            # float() converts numpy scalar → Python float (Pydantic-safe).
            kwargs: dict[str, Any] = {
                "epoch":  epoch,
                "x":      float(arr[i, 0]),
                "y":      float(arr[i, 1]),
                "z":      float(arr[i, 2]),
                "x_dot":  float(arr[i, 3]),
                "y_dot":  float(arr[i, 4]),
                "z_dot":  float(arr[i, 5]),
            }
            if cols == 9:
                kwargs["x_ddot"] = float(arr[i, 6])
                kwargs["y_ddot"] = float(arr[i, 7])
                kwargs["z_ddot"] = float(arr[i, 8])
            lines.append(_OEM.Segment.EphemerisData.EphemerisDataLine(**kwargs))

        return _OEM.Segment.EphemerisData(ephemeris_data_lines=lines)

    def ephemeris_data_from_trajectory(
        self,
        trajectory: Any,
    ) -> OEM.Segment.EphemerisData:
        """Raise ``NotImplementedError``; trajectory conversion requires OSTk.

        Direction: external → domain (not implemented).

        Args:
            trajectory: A trajectory object from an external library.

        Raises:
            NotImplementedError: Always.  Install the ``ostk`` extra
                (``pip install orbit-data-messages[ostk]``) and use
                ``OSTkBackend``.
        """
        raise NotImplementedError(
            "ephemeris_data_from_trajectory requires OSTk. "
            "Install the 'ostk' extra and use OSTkBackend."
        )

    def state_to_line(
        self,
        state: np.ndarray,
        epoch: str,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Convert a 1-D numpy state array and a CCSDS epoch string to a data line.

        Direction: external → domain.

        Args:
            state: A 1-D numpy array of 6 or 9 elements in the order
                ``[x, y, z, x_dot, y_dot, z_dot]`` (with optional
                acceleration appended).
            epoch: A CCSDS §7.5.10 epoch string.

        Returns:
            A fully validated ``EphemerisDataLine``.  Pydantic validation fires
            on construction.

        Raises:
            ValueError: If ``state`` does not have 6 or 9 elements.
        """
        from orbit_data_messages.models.oem import OEM as _OEM  # lazy import

        state = np.asarray(state, dtype=np.float64).ravel()
        if len(state) not in (6, 9):
            raise ValueError(f"state must have 6 or 9 elements; got {len(state)}.")
        kwargs: dict[str, Any] = {
            "epoch":  epoch,
            "x":      float(state[0]),
            "y":      float(state[1]),
            "z":      float(state[2]),
            "x_dot":  float(state[3]),
            "y_dot":  float(state[4]),
            "z_dot":  float(state[5]),
        }
        if len(state) == 9:
            kwargs["x_ddot"] = float(state[6])
            kwargs["y_ddot"] = float(state[7])
            kwargs["z_ddot"] = float(state[8])
        return _OEM.Segment.EphemerisData.EphemerisDataLine(**kwargs)

    # ------------------------------------------------------------------
    # CovarianceBackend — domain → external
    # ------------------------------------------------------------------

    def covariance_to_array(
        self,
        cov: OEM.Segment.CovarianceMatrix,
    ) -> np.ndarray:
        """Convert a ``CovarianceMatrix`` to a float64 numpy array.

        Direction: domain → external.

        Reconstruct the symmetric 6×6 matrix from the 21 lower-triangular
        elements stored in each ``CovarianceMatrixLines`` entry.

        Args:
            cov: A validated ``CovarianceMatrix`` instance.

        Returns:
            A float64 numpy array of shape ``(N, 6, 6)``.
        """
        n = len(cov.covariance_matrix_lines)
        out = np.zeros((n, 6, 6), dtype=np.float64)
        for i, cml in enumerate(cov.covariance_matrix_lines):
            for field, (r, c) in zip(_COV_FIELDS, _COV_POSITIONS):
                v = float(getattr(cml, field))
                out[i, r, c] = v
                out[i, c, r] = v  # symmetric
        return out

    # ------------------------------------------------------------------
    # CovarianceBackend — external → domain  (from_ method)
    # ------------------------------------------------------------------

    def covariance_from_array(
        self,
        arr: np.ndarray,
        epochs: list[str],
        cov_ref_frame: str | None = None,
    ) -> OEM.Segment.CovarianceMatrix:
        """Construct a validated ``CovarianceMatrix`` from a float64 array and epoch strings.

        Direction: external → domain.

        Only lower-triangular elements ``arr[i, r, c]`` are read.
        ``float()`` conversion ensures Pydantic receives Python scalars rather
        than numpy scalars.

        Args:
            arr: A float64 numpy array of shape ``(N, 6, 6)``.
            epochs: A list of N CCSDS §7.5.10 epoch strings.
            cov_ref_frame: Optional reference frame string.  When ``None``, no
                ``COV_REF_FRAME`` keyword is set on the resulting lines.

        Returns:
            A fully validated ``CovarianceMatrix`` instance.  Pydantic
            validation fires on construction.

        Raises:
            ValueError: If ``arr`` is not shape ``(N, 6, 6)`` or
                ``len(arr) != len(epochs)``.
        """
        from orbit_data_messages.models.oem import OEM as _OEM  # lazy import

        arr = np.asarray(arr, dtype=np.float64)
        if arr.ndim != 3 or arr.shape[1:] != (6, 6):
            raise ValueError(
                f"arr must have shape (N, 6, 6); got {arr.shape}."
            )
        if len(arr) != len(epochs):
            raise ValueError(
                f"arr has {len(arr)} matrices but {len(epochs)} epochs."
            )

        lines = []
        for i, epoch in enumerate(epochs):
            kwargs: dict[str, Any] = {"epoch": epoch}
            if cov_ref_frame is not None:
                kwargs["cov_ref_frame"] = cov_ref_frame
            for field, (r, c) in zip(_COV_FIELDS, _COV_POSITIONS):
                # arr[i, r, c] — lower-triangle element → Python float.
                kwargs[field] = float(arr[i, r, c])
            lines.append(
                _OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(**kwargs)
            )
        return _OEM.Segment.CovarianceMatrix(covariance_matrix_lines=lines)
