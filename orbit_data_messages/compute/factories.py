"""
Compute factories for CCSDS Orbit Data Messages.

Factories construct domain models from dynamic sources such as orbit
propagators.  They are standalone functions, not classmethods on domain models.

No backend module is imported at module level — backends are imported lazily
inside each factory so that the factory always works with PurePythonBackend
even when optional extras (numpy, OSTk) are not installed.
"""
from __future__ import annotations

import re
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orbit_data_messages.compute.backends.base import EphemerisBackend
    from orbit_data_messages.models.oem import OEM


# ---------------------------------------------------------------------------
# Internal epoch-string helpers
# ---------------------------------------------------------------------------
# These helpers live in the factory (not imported from backends) so that
# the factory has zero module-level dependencies on optional libraries.

_DOY_RE = re.compile(r"^\d{4}-(\d{3})T")


def _parse_epoch_str(epoch: str) -> datetime:
    """
    Parse a CCSDS §7.5.10 epoch string to a stdlib datetime.
    Handles both calendar (YYYY-MM-DDThh:mm:ss) and DOY (YYYY-DOYThh:mm:ss).
    """
    e = epoch.rstrip("Z")
    if _DOY_RE.match(e):
        date_part, time_part = e.split("T", 1)
        year, doy = int(date_part[:4]), int(date_part[5:8])
        base = datetime(year, 1, 1) + timedelta(days=doy - 1)
        h, m, s = time_part.split(":")
        sf = float(s)
        return datetime(
            base.year, base.month, base.day,
            int(h), int(m), int(sf),
            round((sf % 1) * 1_000_000),
        )
    return datetime.fromisoformat(e)


def _format_epoch_str(dt: datetime) -> str:
    """Format a stdlib datetime to a CCSDS calendar epoch string."""
    s = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        s += f".{dt.microsecond:06d}".rstrip("0")
    return s


def _epoch_string_range(
    start: str,
    stop: str,
    step_seconds: float,
) -> list[str]:
    """
    Generate CCSDS calendar epoch strings from start to stop (inclusive)
    at uniform step_seconds intervals using stdlib only.

    Both §7.5.10 formats (calendar and DOY) are accepted for start/stop;
    output is always in calendar format.
    """
    start_dt = _parse_epoch_str(start)
    stop_dt  = _parse_epoch_str(stop)
    step     = timedelta(seconds=step_seconds)

    result: list[str] = []
    current = start_dt
    while current <= stop_dt:
        result.append(_format_epoch_str(current))
        current = current + step
    return result


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def ephemeris_from_propagator(
    propagator: Callable[[Any], Any],
    start: str,
    stop: str,
    timestep_seconds: float,
    backend: EphemerisBackend | None = None,
) -> OEM.Segment.EphemerisData:
    """
    Build an EphemerisData by calling a propagator at uniform time steps.

    Parameters
    ----------
    propagator
        Any callable with signature ``propagator(epoch: Any) -> state: Any``.
        It receives the epoch in the backend's native type (as returned by
        ``backend.parse_epoch``) and returns a state object that
        ``backend.state_to_line`` can convert to an EphemerisDataLine.
    start
        First epoch to propagate, as a CCSDS §7.5.10 epoch string.
    stop
        Last epoch to propagate (inclusive), as a CCSDS §7.5.10 epoch string.
    timestep_seconds
        Step size in SI seconds.
    backend
        An EphemerisBackend instance.  Defaults to ``PurePythonBackend()``
        so the factory always works without any optional extras installed.

    Returns
    -------
    OEM.Segment.EphemerisData
        A fully validated EphemerisData; Pydantic validation fires on
        construction, including the ``check_epochs_ordered`` validator.

    Notes
    -----
    The factory generates epoch strings with stdlib, converts each to the
    backend's native type via ``backend.parse_epoch``, calls the propagator,
    and converts the resulting state via ``backend.state_to_line``.
    No backend module is imported at the factory's module level.
    """
    if backend is None:
        # Lazy import — keeps the factory module free of optional deps.
        from orbit_data_messages.compute.backends.pure import PurePythonBackend
        backend = PurePythonBackend()

    epoch_strings = _epoch_string_range(start, stop, timestep_seconds)

    if not epoch_strings:
        raise ValueError(
            f"No epochs generated between start='{start}' and stop='{stop}' "
            f"at timestep_seconds={timestep_seconds}. "
            "Verify that start ≤ stop and timestep_seconds > 0."
        )

    lines = []
    for epoch_str in epoch_strings:
        # Convert to backend-native epoch for the propagator call.
        epoch_native = backend.parse_epoch(epoch_str)
        state        = propagator(epoch_native)
        # Convert state + string epoch → validated EphemerisDataLine.
        line = backend.state_to_line(state, epoch_str)
        lines.append(line)

    # Lazy import — domain model only imported when the factory is called.
    from orbit_data_messages.models.oem import OEM as _OEM
    return _OEM.Segment.EphemerisData(ephemeris_data_lines=lines)
