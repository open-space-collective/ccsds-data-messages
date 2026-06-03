# Registry

## I/O adapter registry

Maps `(format, message_type)` pairs to adapter classes using lazy string references.
No adapter module is imported at registry load time - adapters are loaded on first request.

Adding a new adapter requires one new entry in `_READERS` or `_WRITERS` only.

::: orbit_data_messages.io.registry
    options:
      filters: []

## Compute backend registry

Not yet implemented.
