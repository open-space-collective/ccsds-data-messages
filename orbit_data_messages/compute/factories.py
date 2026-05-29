"""
Compute factories for CCSDS Orbit Data Messages.

Factories construct domain models from dynamic sources such as orbit
propagators.  They are standalone functions, not classmethods on domain models.

No backend module is imported at module level — backends are imported lazily
inside each factory so that the factory always works with PurePythonBackend
even when optional extras (numpy, OSTk) are not installed.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from typing import Callable
from typing import TYPE_CHECKING

from orbit_data_messages.models._epoch import format_ccsds_epoch
from orbit_data_messages.models._epoch import parse_ccsds_epoch

if TYPE_CHECKING:
    from orbit_data_messages.compute.backends.base import EphemerisBackend
    from orbit_data_messages.models.oem import OEM


def _epoch_string_range(
    start: str,
    stop: str,
    step_seconds: float,
) -> list[str]:
    """Generate CCSDS calendar epoch strings from start to stop (inclusive).

    Produces epoch strings at uniform ``step_seconds`` intervals. Both
    §7.5.10 formats (calendar and DOY) are accepted for start/stop; output
    is always in calendar format.

    Args:
        start: First epoch as a CCSDS §7.5.10 epoch string.
        stop: Last epoch (inclusive) as a CCSDS §7.5.10 epoch string.
        step_seconds: Interval between epochs in SI seconds.

    Returns:
        Ordered list of CCSDS calendar epoch strings from start to stop.
    """
    start_dt = parse_ccsds_epoch(start)
    stop_dt  = parse_ccsds_epoch(stop)
    step     = timedelta(seconds=step_seconds)

    result: list[str] = []
    current = start_dt
    while current <= stop_dt:
        result.append(format_ccsds_epoch(current))
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
    """Build an EphemerisData by calling a propagator at uniform time steps.

    Generates epoch strings using stdlib, converts each to the backend's native
    type via ``backend.parse_epoch``, calls the propagator, and converts the
    resulting state via ``backend.state_to_line``. No backend module is imported
    at this module's level.

    Args:
        propagator: Any callable with signature
            ``propagator(epoch: Any) -> state: Any``. Receives the epoch in the
            backend's native type (as returned by ``backend.parse_epoch``) and
            returns a state object that ``backend.state_to_line`` can convert to
            an ``EphemerisDataLine``.
        start: First epoch to propagate, as a CCSDS §7.5.10 epoch string.
        stop: Last epoch to propagate (inclusive), as a CCSDS §7.5.10 epoch string.
        timestep_seconds: Step size in SI seconds.
        backend: An ``EphemerisBackend`` instance. Defaults to
            ``PurePythonBackend()`` so the factory always works without any
            optional extras installed.

    Returns:
        A plain ``EphemerisData`` — not a view, not a numpy array. Pydantic
        validation fires on construction, including the
        ``check_epochs_ordered`` validator.

    Raises:
        ValueError: If no epochs are generated between start and stop (e.g.
            start > stop, or timestep_seconds <= 0).
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
