# API reference

Everything documented here is importable from the top-level `ccsds_data_messages`
package (value enums live in `ccsds_data_messages.values`). Private modules, whose
names start with an underscore, are internal and are not part of the public API.

## Reading and writing

```{eval-rst}
.. autofunction:: ccsds_data_messages.read
.. autofunction:: ccsds_data_messages.read_string
.. autofunction:: ccsds_data_messages.write
.. autofunction:: ccsds_data_messages.write_string
```

### Type-specific helpers

```{eval-rst}
.. autofunction:: ccsds_data_messages.read_opm
.. autofunction:: ccsds_data_messages.read_omm
.. autofunction:: ccsds_data_messages.read_oem
.. autofunction:: ccsds_data_messages.read_ocm
.. autofunction:: ccsds_data_messages.write_opm
.. autofunction:: ccsds_data_messages.write_omm
.. autofunction:: ccsds_data_messages.write_oem
.. autofunction:: ccsds_data_messages.write_ocm
```

## Message models

```{eval-rst}
.. autopydantic_model:: ccsds_data_messages.OPM
.. autopydantic_model:: ccsds_data_messages.OMM
.. autopydantic_model:: ccsds_data_messages.OEM
.. autopydantic_model:: ccsds_data_messages.OCM
```

### Abstract base

```{eval-rst}
.. autoclass:: ccsds_data_messages.CCSDSDataMessage
    :members:
```

## Conversions

```{eval-rst}
.. autofunction:: ccsds_data_messages.oem_to_tracss_ocm
```

## Output options

```{eval-rst}
.. autoclass:: ccsds_data_messages.WriterOptions
    :members:
```

## Formats and value types

```{eval-rst}
.. autoclass:: ccsds_data_messages.MessageFormat
    :members:
.. autoclass:: ccsds_data_messages.MessageType
    :members:
```

The CCSDS value enums (reference frames, time systems, center names, and so on) are
defined together:

```{eval-rst}
.. automodule:: ccsds_data_messages.models.values
    :members:
    :undoc-members:
```

## Exceptions

```{eval-rst}
.. automodule:: ccsds_data_messages.exceptions
    :members:
    :show-inheritance:
```

## Extension points

Custom adapters conform to these protocols and register themselves so that `read` and
`write` can dispatch to them.

```{eval-rst}
.. autoclass:: ccsds_data_messages.MessageReaderPort
    :members:
.. autoclass:: ccsds_data_messages.MessageWriterPort
    :members:
.. autofunction:: ccsds_data_messages.io.register_reader
.. autofunction:: ccsds_data_messages.io.register_writer
```
