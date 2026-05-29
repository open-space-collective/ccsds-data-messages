# Computation

The computation layer provides views, backends, and factories for working with ephemeris
data numerically. It is entirely optional — the core read/write functionality works
without any extra installed.

## Design overview

A **backend** translates between OEM domain model types and the types of a specific math
library (numpy arrays, OSTk objects, etc.). A **view** binds an `EphemerisData` or
`CovarianceMatrix` domain model to a backend, exposing iteration, interpolation, and
convenience conversion methods.

The domain model is never mutated — views hold a reference to it and copy nothing.

## Backends

Three backends ship with the package:

| Backend | Extra required | Position type | Trajectory/interpolation |
|---|---|---|---|
| `PurePythonBackend` | none | `list[float]` | `NotImplementedError` |
| `NumpyBackend` | `numpy` | `np.ndarray (3,)` | `NotImplementedError` |
| `OSTkBackend` | `ostk` | OSTk `Position` | OSTk interpolation |

```python
from orbit_data_messages.compute.backends.pure  import PurePythonBackend
from orbit_data_messages.compute.backends.numpy_ import NumpyBackend   # requires numpy
from orbit_data_messages.compute.backends.ostk_  import OSTkBackend    # requires ostk
```

## EphemerisView

`EphemerisView` wraps an `OEM.Segment.EphemerisData` block and a backend. It is:

- **Iterable** — yields one `StateView` per data line.
- **Callable** — interpolates to an arbitrary epoch (delegates to the backend).
- **Convertible** — convenience shortcuts to numpy arrays or OSTk trajectories.

### Basic usage

```python
from orbit_data_messages import Reader
from orbit_data_messages.compute.views import EphemerisView
from orbit_data_messages.compute.backends.numpy_ import NumpyBackend

msg = Reader.read("orbit.oem")
data = msg.segments[0].ephemeris_data

view = EphemerisView(data, backend=NumpyBackend())

# Iterate over states
for state in view:
    print(state.epoch)           # CCSDS epoch string
    print(state.position)        # np.ndarray [x, y, z] in km
    print(state.velocity)        # np.ndarray [x_dot, y_dot, z_dot] in km/s

print(len(view))                 # number of data lines
```

### Conversion to numpy array

```python
arr = view.to_numpy()    # shape (N, 6) without accelerations; (N, 9) with

# Or via the backend directly (equivalent):
from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
arr = NumpyBackend().to_array(data)
```

### Conversion to OSTk trajectory

```python
from orbit_data_messages.compute.backends.ostk_ import OSTkBackend

view_ostk = EphemerisView(data, backend=OSTkBackend())
trajectory = view_ostk.to_ostk()   # OSTk Trajectory object
```

## StateView

`StateView` represents a single ephemeris data line bound to a backend. All properties
delegate to the backend — the view does no computation.

```python
from orbit_data_messages.compute.views import EphemerisView
from orbit_data_messages.compute.backends.numpy_ import NumpyBackend

view = EphemerisView(data, backend=NumpyBackend())
state = next(iter(view))

print(state.epoch)         # "2025-01-01T00:00:00"  (CCSDS string, always)
print(state.position)      # np.ndarray [x, y, z] in km
print(state.velocity)      # np.ndarray [x_dot, y_dot, z_dot] in km/s
print(state.acceleration)  # np.ndarray or None (None when line has no accelerations)
print(state.line)          # the underlying EphemerisDataLine domain model
```

## CovarianceView

`CovarianceView` wraps an `OEM.Segment.CovarianceMatrix` block. It is iterable over
backend-native 6×6 matrices and provides a `to_numpy()` shortcut.

```python
from orbit_data_messages.compute.views import CovarianceView
from orbit_data_messages.compute.backends.numpy_ import NumpyBackend

cov_data = msg.segments[0].covariance_matrix   # may be None if not present
if cov_data is not None:
    cov_view = CovarianceView(cov_data, backend=NumpyBackend())

    # Iterate over 6×6 matrices (one per covariance epoch)
    for matrix in cov_view:
        print(matrix.shape)    # (6, 6) when using NumpyBackend

    # Or get the full (N, 6, 6) array at once
    arr = cov_view.to_numpy()
    print(arr.shape)            # (N, 6, 6)
```

## Explicit backend parameter (recommended)

Always pass `backend=` explicitly. It is unambiguous and works in any execution context:

```python
view = EphemerisView(data, backend=NumpyBackend())
```

## `using_backend` context manager

`using_backend` pushes a named backend onto a thread-local stack for the duration of a
`with` block. Yield the backend and pass it to views explicitly within the block:

```python
from orbit_data_messages.compute.registry import using_backend
from orbit_data_messages.compute.views import EphemerisView

with using_backend("numpy") as b:
    view = EphemerisView(data, backend=b)
    arr = view.to_numpy()
```

Nesting is supported — the inner context overrides the outer, which is restored on exit:

```python
with using_backend("pure") as b_outer:
    with using_backend("numpy") as b_inner:
        # b_inner is active here
        ...
    # b_outer is restored here
```

!!! note "Thread-safety warning"
    `using_backend` is thread-local. It is **not safe for asyncio**: concurrent
    coroutines in the same thread share the same stack, so the context manager cannot
    isolate backends across coroutines. In async code, always pass `backend=` explicitly
    to each view.

## `backend()` helper

Instantiate a named backend directly by name:

```python
from orbit_data_messages.compute.registry import backend

b = backend("numpy")   # NumpyBackend()
b = backend("ostk")    # OSTkBackend()
b = backend("pure")    # PurePythonBackend()
```

## Domain model shortcuts

`EphemerisData` and `CovarianceMatrix` expose `to_*` and `from_*` convenience methods
as one-liner delegates to the relevant backend. These are syntactic sugar only — the
same operations are available through the views and backends directly.

```python
# Convert to numpy
arr = segment.ephemeris_data.to_numpy()          # (N, 6) or (N, 9)
cov_arr = segment.covariance_matrix.to_numpy()   # (N, 6, 6)

# Convert to OSTk
trajectory = segment.ephemeris_data.to_ostk()   # OSTk Trajectory

# Construct domain models from external types
from orbit_data_messages.models.oem import OEM

ephem = OEM.Segment.EphemerisData.from_numpy(arr, epochs)
ephem = OEM.Segment.EphemerisData.from_ostk(ostk_trajectory)
cov   = OEM.Segment.CovarianceMatrix.from_numpy(cov_arr, epochs)
# All return fully validated Pydantic model instances.
```

## Factory: building ephemeris from a propagator

`ephemeris_from_propagator` samples a propagator callback at uniform time steps and
returns a plain `EphemerisData` domain model (not a view):

```python
from orbit_data_messages.compute.factories import ephemeris_from_propagator
from orbit_data_messages.compute.backends.ostk_ import OSTkBackend

def my_propagator(epoch):
    # epoch is the backend's native type (OSTk Instant when using OSTkBackend)
    # return a state object the backend can convert via state_to_line()
    ...

ephem = ephemeris_from_propagator(
    propagator=my_propagator,
    start="2025-01-01T00:00:00",
    stop="2025-01-02T00:00:00",
    timestep_seconds=60.0,
    backend=OSTkBackend(),    # defaults to PurePythonBackend() when omitted
)
# ephem is a fully validated OEM.Segment.EphemerisData
# — epochs are confirmed strictly increasing by the validator.

# Wrap it in a segment and build a full OEM:
from orbit_data_messages.models.oem import OEM

segment = OEM.Segment(
    metadata=OEM.Segment.Metadata(
        object_name="MY SPACECRAFT",
        object_id="2025-001A",
        center_name="EARTH",
        ref_frame="EME2000",
        time_system="UTC",
        start_time="2025-01-01T00:00:00",
        stop_time="2025-01-02T00:00:00",
    ),
    ephemeris_data=ephem,
)
```
