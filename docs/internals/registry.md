# Registry

## I/O adapter registry

Maps `(format, message_type)` pairs to adapter classes using lazy string references.
No adapter module is imported at registry load time — adapters are loaded on first request.

Adding a new adapter requires one new entry in `_READERS` or `_WRITERS` only.

::: orbit_data_messages.io.registry
    options:
      filters: []

## Compute backend registry

Maps backend names to backend classes, and provides a thread-local context manager
for ambient backend selection.

::: orbit_data_messages.compute.registry
    options:
      filters: []
