# Reading and Writing

The primary API is a set of standalone functions exported directly from `orbit_data_messages`.
Format detection, adapter selection, and parsing are handled internally - callers work only
with file paths (or strings) and domain model instances.

## Reading a file

### Auto-detection (recommended)

Pass only the file path. Both the format (`kvn` or `xml`) and the message type (`oem`,
`omm`, `opm`, `ocm`) are inferred automatically from the file extension, filename stem,
and file content, in that order of priority:

```python
from orbit_data_messages import read, OEM, OMM, OPM, OCM

msg = read("telemetry.oem")          # KVN OEM - extension is definitive
msg = read("data.xml")               # XML - format from extension, type from content
msg = read("ephemeris_data.txt")     # KVN OEM - stem keyword "ephemeris" wins
```

The returned value is a fully validated Pydantic model. `isinstance` checks work as
expected:

```python
from orbit_data_messages import read
from orbit_data_messages import CCSDSDataMessage

msg = read("my_file.oem")
assert isinstance(msg, CCSDSDataMessage)    # True for all message types
assert isinstance(msg, OEM)                 # True when the file is an OEM
```

### Explicit overrides

Provide `fmt` and `message_type` when auto-detection would be ambiguous:

```python
from orbit_data_messages import read
from orbit_data_messages import MessageFormat
from orbit_data_messages import MessageType

# Plain-text KVN with no standard extension
msg = read("data.txt", fmt="kvn", message_type="oem")

# Force XML parsing regardless of extension - typed enums also accepted
msg = read("export.dat", fmt=MessageFormat.XML, message_type=MessageType.OMM)
```

Both parameters are keyword-only. When both are provided, no file I/O is performed
for detection - the adapter is selected directly.

### Type-specific readers

Use these when the message type is known at call-site and you want a typed return value:

```python
from orbit_data_messages import read_oem
from orbit_data_messages import read_opm
from orbit_data_messages import read_omm
from orbit_data_messages import read_ocm

oem: OEM = read_oem("orbit.oem")            # returns OEM, auto-detects KVN or XML
opm: OPM = read_opm("params.xml")           # returns OPM
omm: OMM = read_omm("mean.omm", fmt="kvn")  # format override still accepted
ocm: OCM = read_ocm("comprehensive.ocm")
```

### Reading from a string

When the content is already in memory (e.g. fetched over HTTP, read from a database),
use `read_string`. Format and message type are mandatory - there is no file path to
sniff them from:

```python
from orbit_data_messages import read_string
from orbit_data_messages import MessageFormat
from orbit_data_messages import MessageType

msg = read_string(kvn_text, MessageFormat.KVN, MessageType.OPM)
msg = read_string(xml_text, "xml", "oem")   # plain strings also accepted
```

### Error handling

A malformed or spec-violating file raises one of two exceptions:

```python
from pydantic import ValidationError
from orbit_data_messages import read

try:
    msg = read("bad_file.oem")
except ValidationError as e:
    # Field values violated a spec constraint (e.g. epoch out of range,
    # mandatory field missing). e.errors() lists every violation.
    print(e)
except ValueError as e:
    # Format or message type could not be determined, or KVN/XML is
    # structurally malformed (wrong block order, missing delimiter, etc.).
    print(e)
```

`ValidationError` is never swallowed - it propagates unchanged so callers can inspect
individual field violations.

## Writing a file

### Format inference (recommended)

Pass a message object and an output path. The format is inferred from the file extension:
`.xml` produces XML; all other extensions produce KVN.

```python
from orbit_data_messages import write

write(msg, "output.oem")          # KVN (extension .oem)
write(msg, "output.xml")          # XML (extension .xml)
write(msg, "output.omm")          # KVN (extension .omm)
```

### Explicit format override

```python
write(msg, "output.txt", fmt="kvn")     # force KVN
write(msg, "output.dat", fmt="xml")     # force XML
```

### Type-specific writers

```python
from orbit_data_messages import write_oem
from orbit_data_messages import write_opm
from orbit_data_messages import write_omm
from orbit_data_messages import write_ocm

write_oem(oem, "orbit.oem")
write_opm(opm, "params.xml")
write_omm(omm, "mean.omm", fmt="kvn")   # format override still accepted
write_ocm(ocm, "comprehensive.xml")
```

### Writing to a string

Serialize to an in-memory string without touching the filesystem:

```python
from orbit_data_messages import write_string
from orbit_data_messages import MessageFormat

kvn_text: str = write_string(msg, MessageFormat.KVN)
xml_text: str = write_string(msg, "xml")
```

### Formatting options

`WriterOptions` controls output style. The defaults produce human-readable,
spec-recommended output:

```python
from orbit_data_messages import write
from orbit_data_messages import WriterOptions

# Defaults: aligned keywords, column-aligned data, units in XML
write(msg, "output.oem")

# Compact KVN: no keyword alignment, no data column alignment
opts = WriterOptions(align_keywords=False, align_data_columns=False)
write(msg, "output.oem", options=opts)

# Suppress units attributes in XML output
opts = WriterOptions(include_units=False)
write(msg, "output.xml", options=opts)

# Override float precision for specific fields
opts = WriterOptions(float_formats={
    "X": " .6f", "Y": " .6f", "Z": " .6f",
    "X_DOT": " .9f", "Y_DOT": " .9f", "Z_DOT": " .9f",
})
write(msg, "output.oem", options=opts)
```

See [`WriterOptions`](../api/reader-writer.md) for all available options.

## Round-trip example

Reading a KVN OEM, writing to XML, reading back, and comparing:

```python
from orbit_data_messages import read
from orbit_data_messages import write

# Read from KVN
original = read("my_orbit.oem")

# Write to XML
write(original, "my_orbit.xml")

# Read back
roundtrip = read("my_orbit.xml")

# Field values are preserved (floating-point precision notwithstanding)
seg_orig = original.segments[0]
seg_rt   = roundtrip.segments[0]

assert seg_orig.metadata.object_name == seg_rt.metadata.object_name
assert seg_orig.metadata.ref_frame   == seg_rt.metadata.ref_frame
assert len(seg_orig.ephemeris_data.ephemeris_data_lines) == \
       len(seg_rt.ephemeris_data.ephemeris_data_lines)
```

## Accessing message fields

All message fields are plain Python attributes, validated on construction. Example
using OEM:

```python
from orbit_data_messages import read
from orbit_data_messages import OEM

msg: OEM = read("orbit.oem")

# Header
print(msg.header.ccsds_oem_vers)   # "3.0"
print(msg.header.originator)       # "MY-AGENCY"
print(msg.header.creation_date)    # "2025-01-01T00:00:00"

# First segment metadata
meta = msg.segments[0].metadata
print(meta.object_name)            # "MY SPACECRAFT"
print(meta.object_id)              # "2025-001A"
print(meta.center_name)            # CenterName.EARTH  (StrEnum - compares to "EARTH")
print(meta.ref_frame)              # RefFrame.EME2000
print(meta.time_system)            # TimeSystem.UTC
print(meta.start_time)             # "2025-01-01T00:00:00"
print(meta.stop_time)              # "2025-01-02T00:00:00"

# Ephemeris data lines
for line in msg.segments[0].ephemeris_data.ephemeris_data_lines:
    print(line.epoch, line.x, line.y, line.z)      # position in km
    print(line.x_dot, line.y_dot, line.z_dot)      # velocity in km/s
    if line.x_ddot is not None:
        print(line.x_ddot, line.y_ddot, line.z_ddot)  # acceleration in km/s²
```
