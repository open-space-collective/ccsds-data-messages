
# CCSDS Data Messages

A Python library for reading, writing, and validating CCSDS data files that conform to the
[CCSDS 502.0-B-3](https://public.ccsds.org/Pubs/502x0b3e1.pdf) Orbit Data Message (ODM)
standard. The four message types OPM, OMM, OEM, and OCM in both KVN and XML formats.

## Quick start

```python
from orbit_data_messages import read
from orbit_data_messages import write
from orbit_data_messages import OEM

# Read any supported format - format and message type are auto-detected.
msg = read("my_file.oem")
assert isinstance(msg, OEM)

# Access validated fields directly.
segment = msg.segments[0]
print(segment.metadata.object_name)   # "MY SPACECRAFT"
print(segment.metadata.ref_frame)     # "EME2000"

# Write to a different format - inferred from the output extension.
write(msg, "output.xml")        # XML
write(msg, "output.oem")        # KVN

# Override format and message type explicitly.
msg = read("data.txt", fmt="kvn", message_type="oem")
write(msg, "output.txt", fmt="kvn")
```

## What this library is

A faithful, complete implementation of the ODM standard - nothing more, nothing less.
The domain models are the authoritative source of truth. Adding an invalid field value
or missing a mandatory keyword raises a `pydantic.ValidationError` with a message that
cites the relevant spec section.

## What this library is not

An orbital mechanics engine. It does not propagate orbits, evaluate force models, or
make any physical claim about the validity of the data it holds. The physics live in
external libraries such as [Open Space Toolkit](https://github.com/open-space-collective/open-space-toolkit).

## Next steps

- [Reading and Writing](user-guide/reading-and-writing.md) - read and write OEM, OMM, OPM, and OCM files.
- [Formats](user-guide/formats.md) - KVN and XML format reference.
- [API Reference](api/reader-writer.md) - detailed API documentation.
