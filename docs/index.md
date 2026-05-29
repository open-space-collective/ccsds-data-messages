
# CCSDS ODM

A Python library for reading, writing, and validating orbit data files that conform to the
[CCSDS 502.0-B-3](https://public.ccsds.org/Pubs/502x0b3e1.pdf) Orbit Data Message (ODM)
standard — the four message types OPM, OMM, OEM, and OCM in both KVN and XML formats.

This library is a faithful, complete implementation of the standard. The domain models permit
exactly what the spec permits and reject exactly what the spec rejects. No convenience
relaxations, no undocumented extensions. If the spec says a field is mandatory, it is mandatory
here; if the spec says a value must lie within a range, that range is enforced.

## Quick start

```python
from orbit_data_messages import Reader, Writer
from orbit_data_messages import OEM

# Read any supported format — format and message type are auto-detected.
msg = Reader.read("my_file.oem")
assert isinstance(msg, OEM)

# Access validated fields directly.
segment = msg.segments[0]
print(segment.metadata.object_name)   # "MY SPACECRAFT"
print(segment.metadata.ref_frame)     # "EME2000"

# Write to a different format — inferred from the output extension.
Writer.write(msg, "output.xml")        # XML
Writer.write(msg, "output.oem")        # KVN

# Override format and message type explicitly.
msg = Reader.read("data.txt", fmt="kvn", message_type="oem")
Writer.write(msg, "output.txt", fmt="kvn")
```

## What this library is

A faithful, complete implementation of the ODM standard — nothing more, nothing less.
The domain models are the authoritative source of truth. Adding an invalid field value
or missing a mandatory keyword raises a `pydantic.ValidationError` with a message that
cites the relevant spec section.

## What this library is not

An orbital mechanics engine. It does not propagate orbits, evaluate force models, or
make any physical claim about the validity of the data it holds. The optional
[computation layer](user-guide/compute.md) provides interpolation and interoperability
with libraries such as [numpy](https://numpy.org/) and
[Open Space Toolkit](https://github.com/open-space-collective/open-space-toolkit) — but
the physics live in those libraries, not here.

## Next steps

- [Installation](user-guide/installation.md) — install the package and optional extras.
- [Reading and Writing](user-guide/reading-and-writing.md) — read and write OEM, OMM, OPM, and OCM files.
- [Computation](user-guide/compute.md) — use views and backends for numerical operations.
- [Formats](user-guide/formats.md) — KVN and XML format reference.
- [API Reference](api/reader-writer.md) — detailed API documentation.
