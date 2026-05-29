"""
Open Space Toolkit (OSTk) compute backend for the ``orbit_data_messages`` package.

Satisfies ``EphemerisBackend`` and ``CovarianceBackend`` protocols.
Requires the ``ostk`` extra.

The OSTk import is guarded at module top: importing this module raises
``ImportError`` with install instructions if the ``ostk`` extra is not
installed.

Unit conversions:
    OEM uses km and km/s; OSTk uses metres and m/s internally.  All conversion
    factors live in the named constants below and nowhere else.

Fully implemented:
    position, velocity, acceleration, parse_epoch, to_array,
    trajectory_from_ephemeris, ephemeris_data_from_trajectory,
    steps, state_to_line, covariance_to_array, covariance_from_array.

Raises NotImplementedError:
    interpolate  (use OSTk's own propagator instead).
"""
from __future__ import annotations

import re
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# OSTk import guard
# ---------------------------------------------------------------------------

try:
    from ostk.astrodynamics import Trajectory
    from ostk.astrodynamics.trajectory import State
    from ostk.physics.coordinate import Frame
    from ostk.physics.coordinate import Position
    from ostk.physics.coordinate import Velocity
    from ostk.physics.time import DateTime
    from ostk.physics.time import Instant
    from ostk.physics.time import Scale
    from ostk.mathematics.object import RealVector
except ImportError as _err:
    raise ImportError(
        "OSTkBackend requires Open Space Toolkit. "
        "Install it with:  pip install orbit-data-messages[ostk]"
    ) from _err

if TYPE_CHECKING:
    from orbit_data_messages.models.oem import OEM

# ---------------------------------------------------------------------------
# Unit conversion constants.
#
# OEM (CCSDS 502.0-B-3) stores positions in km and velocities in km/s.
# OSTk uses SI units internally: metres for position, m/s for velocity.
# All km ↔ m conversions in this module use only these four constants so
# that the conversion factor is never duplicated or hardcoded elsewhere.
# ---------------------------------------------------------------------------

_KM_TO_M    = 1_000.0   # OEM position: km → OSTk: m
_M_TO_KM    = 1e-3       # OSTk position: m → OEM: km
_KMS_TO_MS  = 1_000.0   # OEM velocity: km/s → OSTk: m/s
_MS_TO_KMS  = 1e-3       # OSTk velocity: m/s → OEM: km/s

# ---------------------------------------------------------------------------
# Covariance LTM layout (same as numpy_ backend — derived from domain model)
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

def _epoch_to_instant(epoch: str) -> Instant:
    """Convert a CCSDS epoch string to an OSTk ``Instant`` in UTC.

    Handles both calendar-date (``YYYY-MM-DDTHH:MM:SS``) and day-of-year
    (``YYYY-DDDTHH:MM:SS``) formats as required by §7.5.10.  A trailing
    ``Z`` is stripped before parsing.

    Args:
        epoch: A CCSDS §7.5.10 epoch string.

    Returns:
        An OSTk ``Instant`` in the UTC scale.
    """
    # §7.5.10 — strip trailing Z, convert DOY format to calendar if needed.
    normalized = epoch.rstrip("Z")

    if re.match(r"^\d{4}-(\d{3})T", normalized):
        date_part, time_part = normalized.split("T", 1)
        year = int(date_part[:4])
        doy  = int(date_part[5:8])
        base = datetime(year, 1, 1) + timedelta(days=doy - 1)
        normalized = f"{base.year:04d}-{base.month:02d}-{base.day:02d}T{time_part}"

    date_str, time_str = normalized.split("T")
    year, month, day = (int(x) for x in date_str.split("-"))
    parts = time_str.split(":")
    hour, minute = int(parts[0]), int(parts[1])
    total_seconds = float(parts[2])
    whole_seconds = int(total_seconds)
    microseconds  = round((total_seconds % 1) * 1_000_000)
    milliseconds  = microseconds // 1_000
    sub_milliseconds = microseconds % 1_000

    dt = DateTime(year, month, day, hour, minute, whole_seconds, milliseconds, sub_milliseconds, 0)
    return Instant.date_time(dt, Scale.UTC)


def _instant_to_epoch(instant: Instant) -> str:
    """Convert an OSTk ``Instant`` to a CCSDS calendar epoch string in UTC.

    Trailing zeros in the fractional-seconds part are stripped so that
    whole-second epochs are formatted without a decimal point.

    Args:
        instant: An OSTk ``Instant``.

    Returns:
        A CCSDS-format calendar epoch string (``YYYY-MM-DDTHH:MM:SS[.f]``)
        without a trailing ``Z``.
    """
    dt: DateTime = instant.get_date_time(Scale.UTC)
    # DateTime attributes: year, month, day, hour, minute, second,
    # millisecond, microsecond (OSTk convention).
    total_microseconds = dt.millisecond * 1_000 + dt.microsecond
    result  = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T"
    result += f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
    if total_microseconds:
        result += f".{total_microseconds:06d}".rstrip("0")
    return result


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

class OSTkBackend:
    """Compute backend using Open Space Toolkit.

    Satisfies ``EphemerisBackend`` and ``CovarianceBackend`` protocols.
    Requires the ``ostk`` extra.

    The GCRF (Geocentric Celestial Reference Frame) is used as the default
    inertial frame when constructing OSTk ``Position`` and ``Velocity``
    objects.  Override ``frame`` on the instance to use a different frame.
    """

    # Reference frame used when building OSTk state objects from OEM data.
    # Override on the instance to use a different frame.
    frame: Any = None  # resolved lazily in _frame()

    def _frame(self) -> Any:
        return self.frame if self.frame is not None else Frame.GCRF()

    # ------------------------------------------------------------------
    # EphemerisBackend — decomposition
    # ------------------------------------------------------------------

    def position(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Position:
        """Return an OSTk ``Position`` in the GCRF frame.

        Direction: domain → external.

        Unit conversion: OEM km × ``_KM_TO_M`` → OSTk m.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            An OSTk ``Position`` object in metres, expressed in the GCRF frame.
        """
        coords = RealVector([
            line.x * _KM_TO_M,
            line.y * _KM_TO_M,
            line.z * _KM_TO_M,
        ])
        return Position.meters(coords, self._frame())

    def velocity(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> Velocity:
        """Return an OSTk ``Velocity`` in the GCRF frame.

        Direction: domain → external.

        Unit conversion: OEM km/s × ``_KMS_TO_MS`` → OSTk m/s.

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            An OSTk ``Velocity`` object in m/s, expressed in the GCRF frame.
        """
        coords = RealVector([
            line.x_dot * _KMS_TO_MS,
            line.y_dot * _KMS_TO_MS,
            line.z_dot * _KMS_TO_MS,
        ])
        return Velocity.meters_per_second(coords, self._frame())

    def acceleration(
        self,
        line: OEM.Segment.EphemerisData.EphemerisDataLine,
    ) -> RealVector | None:
        """Return acceleration components as an OSTk ``RealVector``, or ``None``.

        Direction: domain → external.

        Unit conversion: OEM km/s² × ``_KMS_TO_MS`` → OSTk m/s².

        Args:
            line: A validated ``EphemerisDataLine``.

        Returns:
            An OSTk ``RealVector`` of acceleration components in m/s², or
            ``None`` when the line carries no acceleration.
        """
        if line.x_ddot is None:
            return None
        return RealVector([
            line.x_ddot * _KMS_TO_MS,
            line.y_ddot * _KMS_TO_MS,
            line.z_ddot * _KMS_TO_MS,
        ])

    def parse_epoch(self, epoch: str) -> Instant:
        """Parse a CCSDS §7.5.10 epoch string to an OSTk ``Instant`` (UTC).

        Direction: external string → OSTk epoch type.

        Args:
            epoch: A CCSDS-format epoch string.

        Returns:
            An OSTk ``Instant`` in the UTC scale.
        """
        return _epoch_to_instant(epoch)

    # ------------------------------------------------------------------
    # EphemerisBackend — domain → external
    # ------------------------------------------------------------------

    def to_array(self, data: OEM.Segment.EphemerisData) -> list[list[float]]:
        """Convert ``EphemerisData`` to a nested list of floats in OEM units.

        Direction: domain → external.

        Values are left in OEM units (km, km/s) — no unit conversion is
        applied.  Use ``trajectory_from_ephemeris`` to get an OSTk-native
        representation with SI units.

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
            if line.x_ddot is not None:
                row += [line.x_ddot, line.y_ddot, line.z_ddot]
            result.append(row)
        return result

    def trajectory_from_ephemeris(
        self,
        data: OEM.Segment.EphemerisData,
    ) -> Trajectory:
        """Build an OSTk ``Trajectory`` from ``EphemerisData``.

        Direction: domain → external.

        Unit conversion: OEM km → OSTk m (× ``_KM_TO_M``);
        OEM km/s → OSTk m/s (× ``_KMS_TO_MS``).  All conversions use the
        named constants defined at module level.

        Args:
            data: A validated ``EphemerisData`` instance.

        Returns:
            An OSTk ``Trajectory`` constructed from one ``State`` per data line.
        """
        states: list[State] = []
        for line in data.ephemeris_data_lines:
            instant = _epoch_to_instant(line.epoch)
            pos     = self.position(line)   # uses _KM_TO_M internally
            vel     = self.velocity(line)   # uses _KMS_TO_MS internally
            states.append(State(instant, pos, vel))
        return Trajectory(states)

    # ------------------------------------------------------------------
    # EphemerisBackend — interpolation and sampling
    # ------------------------------------------------------------------

    def interpolate(
        self,
        data: OEM.Segment.EphemerisData,
        epoch: Any,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Raise ``NotImplementedError``; use OSTk's own trajectory interpolation.

        Direction: domain + external epoch → domain (not implemented).

        Args:
            data: A validated ``EphemerisData`` instance.
            epoch: The target epoch.

        Raises:
            NotImplementedError: Always.  Call ``trajectory_from_ephemeris``
                to obtain an OSTk ``Trajectory``, then use the trajectory's
                own state-at-instant method.
        """
        raise NotImplementedError(
            "Use trajectory_from_ephemeris to get an OSTk Trajectory, "
            "then use the OSTk Trajectory's own state-at-instant method."
        )

    def steps(
        self,
        start: Instant,
        stop: Instant,
        step: float,
    ) -> list[Instant]:
        """Generate OSTk ``Instant`` values from ``start`` to ``stop``.

        Args:
            start: Start epoch as an OSTk ``Instant``.
            stop: Stop epoch as an OSTk ``Instant`` (inclusive).
            step: Step size in seconds.

        Returns:
            A list of OSTk ``Instant`` values covering the interval.
        """
        from ostk.physics.time import Duration
        result: list[Instant] = []
        delta   = Duration.seconds(step)
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

        Delegates to ``PurePythonBackend`` for the actual construction.

        Args:
            arr: An (N, 6) or (N, 9) nested list of floats.
            epochs: A list of N CCSDS §7.5.10 epoch strings.

        Returns:
            A fully validated ``EphemerisData`` instance.  Pydantic validation
            fires on construction.
        """
        from orbit_data_messages.compute.backends.pure import PurePythonBackend
        return PurePythonBackend().ephemeris_data_from_array(arr, epochs)

    def ephemeris_data_from_trajectory(
        self,
        trajectory: Trajectory,
    ) -> OEM.Segment.EphemerisData:
        """Convert an OSTk ``Trajectory`` to a validated ``EphemerisData``.

        Direction: external → domain.

        Unit conversion: OSTk m → OEM km (× ``_M_TO_KM``);
        OSTk m/s → OEM km/s (× ``_MS_TO_KMS``).  The OSTk ``Instant`` for
        each state is converted to a CCSDS epoch string before being stored
        in the domain model.

        Args:
            trajectory: An OSTk ``Trajectory`` instance.

        Returns:
            A fully validated ``EphemerisData`` instance.  Pydantic validation
            fires on construction.
        """
        from orbit_data_messages.models.oem import OEM as _OEM

        lines = []
        for state in trajectory.get_states():
            instant  = state.get_instant()
            pos      = state.get_position().get_coordinates()   # [m, m, m]
            vel      = state.get_velocity().get_coordinates()   # [m/s, m/s, m/s]
            epoch_str = _instant_to_epoch(instant)

            # Unit conversion: OSTk m → OEM km (×_M_TO_KM).
            line = _OEM.Segment.EphemerisData.EphemerisDataLine(
                epoch=epoch_str,
                x    =float(pos[0]) * _M_TO_KM,
                y    =float(pos[1]) * _M_TO_KM,
                z    =float(pos[2]) * _M_TO_KM,
                x_dot=float(vel[0]) * _MS_TO_KMS,
                y_dot=float(vel[1]) * _MS_TO_KMS,
                z_dot=float(vel[2]) * _MS_TO_KMS,
            )
            lines.append(line)
        return _OEM.Segment.EphemerisData(ephemeris_data_lines=lines)

    def state_to_line(
        self,
        state: State,
        epoch: str,
    ) -> OEM.Segment.EphemerisData.EphemerisDataLine:
        """Convert an OSTk ``State`` and a CCSDS epoch string to a data line.

        Direction: external → domain.

        Unit conversion: OSTk m → OEM km (× ``_M_TO_KM``);
        OSTk m/s → OEM km/s (× ``_MS_TO_KMS``).

        Args:
            state: An OSTk ``State`` object.
            epoch: A CCSDS §7.5.10 epoch string.

        Returns:
            A fully validated ``EphemerisDataLine``.  Pydantic validation fires
            on construction.
        """
        from orbit_data_messages.models.oem import OEM as _OEM

        pos = state.get_position().get_coordinates()
        vel = state.get_velocity().get_coordinates()
        return _OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epoch,
            x    =float(pos[0]) * _M_TO_KM,
            y    =float(pos[1]) * _M_TO_KM,
            z    =float(pos[2]) * _M_TO_KM,
            x_dot=float(vel[0]) * _MS_TO_KMS,
            y_dot=float(vel[1]) * _MS_TO_KMS,
            z_dot=float(vel[2]) * _MS_TO_KMS,
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

        No unit conversion is applied.  Delegates to ``PurePythonBackend``.

        Args:
            cov: A validated ``CovarianceMatrix`` instance.

        Returns:
            An (N, 6, 6) nested list of Python floats.
        """
        from orbit_data_messages.compute.backends.pure import PurePythonBackend
        return PurePythonBackend().covariance_to_array(cov)

    # ------------------------------------------------------------------
    # CovarianceBackend — external → domain
    # ------------------------------------------------------------------

    def covariance_from_array(
        self,
        arr: list[list[list[float]]],
        epochs: list[str],
        cov_ref_frame: str | None = None,
    ) -> OEM.Segment.CovarianceMatrix:
        """Construct a validated ``CovarianceMatrix`` from a nested list and epoch strings.

        Direction: external → domain.

        Delegates to ``PurePythonBackend`` for the actual construction.

        Args:
            arr: An (N, 6, 6) nested list of floats.
            epochs: A list of N CCSDS §7.5.10 epoch strings.
            cov_ref_frame: Optional reference frame string.

        Returns:
            A fully validated ``CovarianceMatrix`` instance.  Pydantic
            validation fires on construction.
        """
        from orbit_data_messages.compute.backends.pure import PurePythonBackend
        return PurePythonBackend().covariance_from_array(arr, epochs, cov_ref_frame)
