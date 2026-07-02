# Installation and usage

## Install

```bash
pip install ccsds-data-messages
```

The package requires Python 3.11 or newer. Its only runtime dependencies are
`pydantic` and `defusedxml`.

## Read and write files

```python
from ccsds_data_messages import read, write, OEM

# The format and message type are auto-detected from the content.
msg = read("my_file.oem")
assert isinstance(msg, OEM)

# Access validated fields directly.
segment = msg.segments[0]
print(segment.metadata.object_name)   # for example "MY SPACECRAFT"
print(segment.metadata.ref_frame)     # for example "EME2000"

# Write to a different format, inferred from the output file extension.
write(msg, "output.xml")        # XML
write(msg, "output.oem")        # KVN

# Specify the format and message type explicitly when needed.
msg = read("data.txt", fmt="kvn", message_type="oem")
write(msg, "output.txt", fmt="kvn")
```

## Work in memory

Every message type (OPM, OMM, OEM, OCM) can be serialized to a string with the generic
`write_string`, in either format. Unlike `write`, it needs an explicit format because
there is no filename to infer one from. The type-specific helpers (`write_opm` and the
rest) write files only; there are no `write_opm_string`-style variants.

```python
from ccsds_data_messages import read_string, write_string, MessageFormat, MessageType

kvn_text = write_string(msg, MessageFormat.KVN)   # or "kvn"
xml_text = write_string(msg, MessageFormat.XML)   # or "xml"

msg = read_string(kvn_text, MessageFormat.KVN, MessageType.OPM)
```

## Construct a message

Each message type has a fluent builder:

```python
from ccsds_data_messages import OPM
from ccsds_data_messages.values import CenterName, RefFrame, TimeSystem

opm = (
    OPM.builder()
    .header(originator="LOFT")
    .metadata(
        object_name="ISS", object_id="1998-067A",
        center_name=CenterName.EARTH, ref_frame=RefFrame.GCRF,
        time_system=TimeSystem.UTC,
    )
    .state_vector(
        epoch="2024-001T00:00:00.000Z",
        x=6778.0, y=0.0, z=0.0,
        x_dot=0.0, y_dot=7.784, z_dot=0.0,
    )
    .build()
)
```

## Validation and errors

Reading a file runs the same validation as constructing a model directly. A malformed
or non-conformant file raises before you get a partially built object back. Unknown
keywords are rejected rather than silently dropped.

All library-raised exceptions inherit from `CCSDSError`. See {doc}`api` for the full
exception hierarchy and for `WriterOptions`, which controls output formatting.
