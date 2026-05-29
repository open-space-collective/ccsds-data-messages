# Backends

Backends translate between OEM domain model types and the types of an external math
library. Each backend owns both conversion directions: domain → external (`to_` methods
and `trajectory_from_ephemeris`) and external → domain (`from_` methods and
`ephemeris_data_from_trajectory`).

`from_` methods always return fully validated Pydantic domain model instances — Pydantic
validation fires on construction.

## Backend protocols

The protocols define the interface every backend must satisfy structurally (no explicit
inheritance required).

::: orbit_data_messages.compute.backends.base.EphemerisBackend

::: orbit_data_messages.compute.backends.base.CovarianceBackend

## PurePythonBackend

::: orbit_data_messages.compute.backends.pure.PurePythonBackend

## NumpyBackend

Requires the `numpy` extra: `pip install orbit-data-messages[numpy]`

::: orbit_data_messages.compute.backends.numpy_.NumpyBackend

## OSTkBackend

Requires the `ostk` extra: `pip install orbit-data-messages[ostk]`

::: orbit_data_messages.compute.backends.ostk_.OSTkBackend
