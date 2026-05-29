# Factories

Factories construct domain models from dynamic sources such as orbit propagators.
They are standalone functions — not classmethods on domain models.

Factories return plain domain model instances (not views, not arrays). The `backend`
parameter defaults to `PurePythonBackend()`, so factories always work without any
optional extras installed.

## ephemeris_from_propagator

::: orbit_data_messages.compute.factories.ephemeris_from_propagator
