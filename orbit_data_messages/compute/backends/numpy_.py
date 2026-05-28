"""
NumPy compute backend.

Implements EphemerisBackend and CovarianceBackend using numpy arrays.

The numpy import is guarded at module top: importing this module raises
ImportError with install instructions if numpy is not available.

Fully implemented
-----------------
position, velocity, acceleration, parse_epoch, to_array, steps,
state_to_line, ephemeris_data_from_array,
covariance_to_array, covariance_from_array.

Raises NotImplementedError
--------------------------
trajectory_from_ephemeris, interpolate, ephemeris_data_from_trajectory
(these require an interpolation library or OSTk; use OSTkBackend instead).
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
    """Return (field_names, (row,col) positions) for the 21 LTM elements."""
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
    """Parse a CCSDS §7.5.10 epoch string to np.datetime64."""
    return np.datetime64(epoch.rstrip("Z").replace("Z", ""))


def _from_datetime64(dt64: np.datetime64) -> str:
    """Format a np.datetime64 to a CCSDS calendar epoch string."""
    # Normalise to microsecond precision then format.
    s = str(np.datetime64(dt64, "us"))
    # np formats as '2025-01-01T00:00:00.000000' — strip trailing zeros.
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

class NumpyBackend:
    """
    Compute backend using numpy.

    Satisfies EphemerisBackend and CovarianceBackend protocols structurally.
    """

    # ------------------------------------------------------------------
    # EphemerisBackend — decomposition
    # ------------------------------------------------------------------

    def position(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> np.ndarray:
        """Return position vector as a (3,) float64 array in km."""
        return np.array([line.x, line.y, line.z], dtype=np.float64)

    def velocity(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> np.ndarray:
        """Return velocity vector as a (3,) float64 array in km/s."""
        return np.array([line.x_dot, line.y_dot, line.z_dot], dtype=np.float64)

    def acceleration(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> np.ndarray | None:
        """Return acceleration vector as a (3,) float64 array in km/s², or None."""
        if line.x_ddot is None:
            return None
        return np.array([line.x_ddot, line.y_ddot, line.z_ddot], dtype=np.float64)

    def parse_epoch(self, epoch: str) -> np.datetime64:
        """Parse a CCSDS §7.5.10 epoch string to np.datetime64 (microsecond)."""
        return _to_datetime64(epoch)

    # ------------------------------------------------------------------
    # EphemerisBackend — domain → external
    # ------------------------------------------------------------------

    def to_array(self, data: OEM.Segment.EphemerisData) -> np.ndarray:
        """
        Return a (N, 6) or (N, 9) float64 array.

        Shape (N, 6) when no line carries acceleration components;
        shape (N, 9) when every line carries them.  Not always one or the
        other: determined per-segment from the actual data.
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
        """
        Generate epoch values from start to stop (inclusive) at step seconds.
        start and stop must be np.datetime64 (as returned by parse_epoch).
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
        """
        Construct a validated EphemerisData from a (N, 6|9) float64 array
        and CCSDS epoch strings.

        Numpy scalars are explicitly converted to Python float before being
        passed to the domain model, so Pydantic receives plain Python types.
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
        raise NotImplementedError(
            "ephemeris_data_from_trajectory requires OSTk. "
            "Install the 'ostk' extra and use OSTkBackend."
        )

    def state_to_line(
        self,
        state: np.ndarray,
        epoch: str,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """
        Convert a 1-D numpy array of 6 or 9 elements and a CCSDS epoch string
        to a validated EphemerisDataLine.
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
        """
        Return a (N, 6, 6) float64 array.

        The symmetric 6×6 matrix is reconstructed from the 21 LTM elements
        stored in each CovarianceMatrixLines entry.
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
        """
        Construct a validated CovarianceMatrix from a (N, 6, 6) float64
        array and CCSDS epoch strings.

        Only lower-triangular elements arr[i, r, c] are read.
        float() conversion ensures Pydantic receives Python scalars.
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
