"""
Pure-Python compute backend for the ``orbit_data_messages`` package.

Satisfies ``EphemerisBackend`` and ``CovarianceBackend`` protocols.
Requires no optional dependencies.

Every test that requires a backend can use ``PurePythonBackend`` without
installing any extra.  Methods that need a numerical library raise
``NotImplementedError`` with a clear message that names the required extra.

Fully implemented:
    position, velocity, acceleration, parse_epoch, to_array, steps,
    ephemeris_data_from_array, covariance_to_array, covariance_from_array.

Raises NotImplementedError:
    trajectory_from_ephemeris, interpolate, ephemeris_data_from_trajectory,
    state_to_line  (each names the extra that would enable it).
"""
from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import TYPE_CHECKING

from orbit_data_messages.models._epoch import format_ccsds_epoch
from orbit_data_messages.models._epoch import parse_ccsds_epoch

if TYPE_CHECKING:
    from orbit_data_messages.models.oem import OEM


# ---------------------------------------------------------------------------
# Covariance LTM layout — 21 fields in spec-mandated order (§5.2.5.4)
# ---------------------------------------------------------------------------

_COV_FIELDS = [
    "cx_x",
    "cy_x",       "cy_y",
    "cz_x",       "cz_y",       "cz_z",
    "cx_dot_x",   "cx_dot_y",   "cx_dot_z",   "cx_dot_x_dot",
    "cy_dot_x",   "cy_dot_y",   "cy_dot_z",   "cy_dot_x_dot", "cy_dot_y_dot",
    "cz_dot_x",   "cz_dot_y",   "cz_dot_z",   "cz_dot_x_dot", "cz_dot_y_dot", "cz_dot_z_dot",
]

# (row, col) 0-indexed positions in the 6×6 lower-triangular matrix.
_COV_POSITIONS: list[tuple[int, int]] = [
    (0, 0),
    (1, 0), (1, 1),
    (2, 0), (2, 1), (2, 2),
    (3, 0), (3, 1), (3, 2), (3, 3),
    (4, 0), (4, 1), (4, 2), (4, 3), (4, 4),
    (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5),
]


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

class PurePythonBackend:
    """Compute backend using Python stdlib only.

    Satisfies ``EphemerisBackend`` and ``CovarianceBackend`` protocols.
    Requires no optional dependencies.
    """

    # ------------------------------------------------------------------
    # EphemerisBackend — decomposition
    # ------------------------------------------------------------------

    def position(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> list[float]:
        """Return the position vector as a plain list.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            ``[x, y, z]`` in km.
        """
        return [line.x, line.y, line.z]

    def velocity(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> list[float]:
        """Return the velocity vector as a plain list.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            ``[x_dot, y_dot, z_dot]`` in km/s.
        """
        return [line.x_dot, line.y_dot, line.z_dot]

    def acceleration(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> list[float] | None:
        """Return the acceleration vector as a plain list, or ``None`` if absent.

        Direction: domain → external.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            ``[x_ddot, y_ddot, z_ddot]`` in km/s², or ``None`` when any
            component is missing.
        """
        if line.x_ddot is None or line.y_ddot is None or line.z_ddot is None:
            return None
        return [line.x_ddot, line.y_ddot, line.z_ddot]

    def parse_epoch(self, epoch: str) -> datetime:
        """Parse a CCSDS §7.5.10 epoch string to a stdlib ``datetime``.

        Direction: external string → stdlib datetime.

        Args:
            epoch: A CCSDS-format epoch string.

        Returns:
            A timezone-naive ``datetime`` in UTC.
        """
        return parse_ccsds_epoch(epoch)

    # ------------------------------------------------------------------
    # EphemerisBackend — domain → external
    # ------------------------------------------------------------------

    def to_array(
        self,
        data: OEM.Segment.EphemerisData,
    ) -> list[list[float]]:
        """Convert ``EphemerisData`` to a nested list of floats.

        Direction: domain → external.

        Each row is ``[x, y, z, x_dot, y_dot, z_dot]`` or, when every data
        line carries accelerations,
        ``[x, y, z, x_dot, y_dot, z_dot, x_ddot, y_ddot, z_ddot]``.

        Args:
            data: A validated ``EphemerisData`` instance.

        Returns:
            An (N, 6) or (N, 9) nested list of Python floats.
        """
        result: list[list[float]] = []
        for line in data.ephemeris_data_lines:
            row: list[float] = [
                line.x, line.y, line.z,
                line.x_dot, line.y_dot, line.z_dot,
            ]
            if line.x_ddot is not None and line.y_ddot is not None and line.z_ddot is not None:
                row += [line.x_ddot, line.y_ddot, line.z_ddot]
            result.append(row)
        return result

    def trajectory_from_ephemeris(
        self,
        data: OEM.Segment.EphemerisData,
    ) -> Any:
        """Raise ``NotImplementedError``; trajectory construction requires a numerical library.

        Direction: domain → external (not implemented).

        Args:
            data: A validated ``EphemerisData`` instance.

        Raises:
            NotImplementedError: Always.  Install the ``ostk`` extra
                (``pip install orbit-data-messages[ostk]``) and use
                ``OSTkBackend``, or the ``numpy`` extra
                (``pip install orbit-data-messages[numpy]``) and use
                ``NumpyBackend``.
        """
        raise NotImplementedError(
            "trajectory_from_ephemeris requires a numerical library. "
            "Install the 'ostk' extra and use OSTkBackend, or the 'numpy' "
            "extra and use NumpyBackend."
        )

    # ------------------------------------------------------------------
    # EphemerisBackend — interpolation and sampling
    # ------------------------------------------------------------------

    def interpolate(
        self,
        data: OEM.Segment.EphemerisData,
        epoch: Any,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Raise ``NotImplementedError``; interpolation requires a numerical library.

        Direction: domain + external epoch → domain (not implemented).

        Args:
            data: A validated ``EphemerisData`` instance.
            epoch: The target epoch.

        Raises:
            NotImplementedError: Always.  Install the ``numpy`` extra
                (``pip install orbit-data-messages[numpy]``) and use
                ``NumpyBackend``.
        """
        raise NotImplementedError(
            "interpolate requires a numerical library. "
            "Install the 'numpy' extra and use NumpyBackend."
        )

    def steps(
        self,
        start: Any,
        stop: Any,
        step: float,
    ) -> list[datetime]:
        """Generate epoch values from ``start`` to ``stop`` at ``step`` seconds.

        ``start`` and ``stop`` must be ``datetime`` objects as returned by
        ``parse_epoch``.

        Args:
            start: Start epoch as a ``datetime``.
            stop: Stop epoch as a ``datetime`` (inclusive).
            step: Step size in seconds.

        Returns:
            A list of ``datetime`` values covering the interval.

        Raises:
            TypeError: If ``start`` or ``stop`` are not ``datetime`` instances.
        """
        if not isinstance(start, datetime) or not isinstance(stop, datetime):
            raise TypeError(
                "PurePythonBackend.steps expects datetime objects "
                "(as returned by parse_epoch)."
            )
        result: list[datetime] = []
        delta   = timedelta(seconds=step)
        current = start
        while current <= stop:
            result.append(current)
            current = current + delta
        return result

    # ------------------------------------------------------------------
    # EphemerisBackend — external → domain  (from_ methods)
    # ------------------------------------------------------------------

    def ephemeris_data_from_array(
        self,
        arr: list[list[float]],
        epochs: list[str],
    ) -> OEM.Segment.EphemerisData:
        """Construct a validated ``EphemerisData`` from a nested list and epoch strings.

        Direction: external → domain.

        Args:
            arr: An (N, 6) or (N, 9) nested list.  Columns are
                ``[x, y, z, x_dot, y_dot, z_dot]`` with optional acceleration
                appended.
            epochs: A list of N CCSDS §7.5.10 epoch strings.

        Returns:
            A fully validated ``EphemerisData`` instance.  Pydantic validation
            fires on construction.

        Raises:
            ValueError: If ``len(arr) != len(epochs)`` or any row does not
                have exactly 6 or 9 elements.
        """
        from orbit_data_messages.models.oem import OEM as _OEM  # lazy import

        if len(arr) != len(epochs):
            raise ValueError(
                f"arr and epochs must have the same length "
                f"(got {len(arr)} rows and {len(epochs)} epochs)."
            )
        lines = []
        for epoch, row in zip(epochs, arr):
            n = len(row)
            if n == 6:
                line = _OEM.Segment.EphemerisData.EphemerisDataLine(
                    epoch=epoch,
                    x=float(row[0]), y=float(row[1]), z=float(row[2]),
                    x_dot=float(row[3]), y_dot=float(row[4]), z_dot=float(row[5]),
                )
            elif n == 9:
                line = _OEM.Segment.EphemerisData.EphemerisDataLine(
                    epoch=epoch,
                    x=float(row[0]), y=float(row[1]), z=float(row[2]),
                    x_dot=float(row[3]), y_dot=float(row[4]), z_dot=float(row[5]),
                    x_ddot=float(row[6]), y_ddot=float(row[7]), z_ddot=float(row[8]),
                )
            else:
                raise ValueError(
                    f"Each row must have 6 (pos+vel) or 9 (pos+vel+acc) "
                    f"elements; row for epoch '{epoch}' has {n}."
                )
            lines.append(line)
        return _OEM.Segment.EphemerisData(ephemeris_data_lines=lines)

    def ephemeris_data_from_trajectory(
        self,
        trajectory: Any,
    ) -> OEM.Segment.EphemerisData:
        """Raise ``NotImplementedError``; trajectory conversion requires an external library.

        Direction: external → domain (not implemented).

        Args:
            trajectory: A trajectory object from an external library.

        Raises:
            NotImplementedError: Always.  Install the ``ostk`` extra
                (``pip install orbit-data-messages[ostk]``) and use
                ``OSTkBackend``.
        """
        raise NotImplementedError(
            "ephemeris_data_from_trajectory requires a trajectory object from "
            "an external library. Install the 'ostk' extra and use OSTkBackend."
        )

    def state_to_line(
        self,
        state: Any,
        epoch: str,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Raise ``NotImplementedError``; state conversion requires an external library.

        Direction: external → domain (not implemented).

        Args:
            state: A state object from an external library.
            epoch: A CCSDS §7.5.10 epoch string.

        Raises:
            NotImplementedError: Always.  Install the ``numpy`` extra
                (``pip install orbit-data-messages[numpy]``) or the ``ostk``
                extra (``pip install orbit-data-messages[ostk]``).
        """
        raise NotImplementedError(
            "state_to_line requires a state object from an external library. "
            "Install the 'numpy' or 'ostk' extra."
        )

    # ------------------------------------------------------------------
    # CovarianceBackend — domain → external
    # ------------------------------------------------------------------

    def covariance_to_array(
        self,
        cov: OEM.Segment.CovarianceMatrix,
    ) -> list[list[list[float]]]:
        """Convert a ``CovarianceMatrix`` to a nested list of floats.

        Direction: domain → external.

        Reconstruct the symmetric 6×6 matrix from the 21 lower-triangular
        elements stored in each ``CovarianceMatrixLines`` entry.

        Args:
            cov: A validated ``CovarianceMatrix`` instance.

        Returns:
            An (N, 6, 6) nested list of Python floats.
        """
        result: list[list[list[float]]] = []
        for cml in cov.covariance_matrix_lines:
            matrix: list[list[float]] = [[0.0] * 6 for _ in range(6)]
            for field, (r, c) in zip(_COV_FIELDS, _COV_POSITIONS):
                v = float(getattr(cml, field))
                matrix[r][c] = v
                matrix[c][r] = v  # symmetric
            result.append(matrix)
        return result

    # ------------------------------------------------------------------
    # CovarianceBackend — external → domain  (from_ method)
    # ------------------------------------------------------------------

    def covariance_from_array(
        self,
        arr: list[list[list[float]]],
        epochs: list[str],
        cov_ref_frame: str | None = None,
    ) -> OEM.Segment.CovarianceMatrix:
        """Construct a validated ``CovarianceMatrix`` from a nested list and epoch strings.

        Direction: external → domain.

        Only the lower-triangular elements are read from each 6×6 matrix.

        Args:
            arr: An (N, 6, 6) nested list of floats.
            epochs: A list of N CCSDS §7.5.10 epoch strings.
            cov_ref_frame: Optional reference frame string.  When ``None``, no
                ``COV_REF_FRAME`` keyword is set on the resulting lines.

        Returns:
            A fully validated ``CovarianceMatrix`` instance.  Pydantic
            validation fires on construction.

        Raises:
            ValueError: If ``len(arr) != len(epochs)``.
        """
        from orbit_data_messages.models.oem import OEM as _OEM  # lazy import

        if len(arr) != len(epochs):
            raise ValueError(
                f"arr and epochs must have the same length "
                f"(got {len(arr)} matrices and {len(epochs)} epochs)."
            )
        lines = []
        for epoch, matrix in zip(epochs, arr):
            kwargs: dict[str, Any] = {"epoch": epoch}
            if cov_ref_frame is not None:
                kwargs["cov_ref_frame"] = cov_ref_frame
            for field, (r, c) in zip(_COV_FIELDS, _COV_POSITIONS):
                kwargs[field] = float(matrix[r][c])
            lines.append(
                _OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(**kwargs)
            )
        return _OEM.Segment.CovarianceMatrix(covariance_matrix_lines=lines)
