# I/O Adapters

Format-specific reader and writer implementations. Each adapter satisfies
`MessageReaderPort` or `MessageWriterPort` structurally (no explicit inheritance).

Keyword strings are never hardcoded in adapters — they are read from `FieldMetadata`
annotations on the domain model. Block delimiter names are read from `Delineation`
`ClassVar` attributes on nested model classes.

## KVN adapters

### OEM

::: orbit_data_messages.io.kvn.oem_reader
    options:
      filters: []

::: orbit_data_messages.io.kvn.oem_writer
    options:
      filters: []

### OMM

::: orbit_data_messages.io.kvn.omm_reader
    options:
      filters: []

::: orbit_data_messages.io.kvn.omm_writer
    options:
      filters: []

### OPM

::: orbit_data_messages.io.kvn.opm_reader
    options:
      filters: []

::: orbit_data_messages.io.kvn.opm_writer
    options:
      filters: []

### OCM

::: orbit_data_messages.io.kvn.ocm_reader
    options:
      filters: []

::: orbit_data_messages.io.kvn.ocm_writer
    options:
      filters: []

### KVN utilities

::: orbit_data_messages.io.kvn._utils
    options:
      filters: []

## XML adapters

### OEM

::: orbit_data_messages.io.xml.oem_reader
    options:
      filters: []

::: orbit_data_messages.io.xml.oem_writer
    options:
      filters: []

### OMM

::: orbit_data_messages.io.xml.omm_reader
    options:
      filters: []

::: orbit_data_messages.io.xml.omm_writer
    options:
      filters: []

### OPM

::: orbit_data_messages.io.xml.opm_reader
    options:
      filters: []

::: orbit_data_messages.io.xml.opm_writer
    options:
      filters: []

### OCM

::: orbit_data_messages.io.xml.ocm_reader
    options:
      filters: []

::: orbit_data_messages.io.xml.ocm_writer
    options:
      filters: []

### XML utilities

::: orbit_data_messages.io.xml._utils
    options:
      filters: []
