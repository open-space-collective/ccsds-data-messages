# ccsds-data-messages

A Python library to read, write, and validate CCSDS Orbit Data Messages (ODM) -
OEM, OMM, OPM, and OCM - in both KVN and XML formats.

Implements CCSDS 502.0-B-3. The domain models permit exactly what the spec permits
and reject exactly what the spec rejects.

## Installation

```bash
pip install ccsds-data-messages
```

## Quick start

```python
from ccsds_data_messages import read, write, OEM

# Read any supported format - format and message type are auto-detected.
msg = read("my_file.oem")
assert isinstance(msg, OEM)

# Access validated fields directly.
segment = msg.segments[0]
print(segment.metadata.object_name)   # e.g. "MY SPACECRAFT"
print(segment.metadata.ref_frame)     # e.g. "EME2000"

# Write to a different format - inferred from the output file extension.
write(msg, "output.xml")        # XML
write(msg, "output.oem")        # KVN

# Specify format and message type explicitly when needed.
msg = read("data.txt", fmt="kvn", message_type="oem")
write(msg, "output.txt", fmt="kvn")
```

## Supported message types

| Type | Description |
|------|-------------|
| OPM  | Orbit Parameter Message - single-epoch Cartesian state |
| OMM  | Orbit Mean-Elements Message - mean Keplerian elements (TLE-compatible) |
| OEM  | Orbit Ephemeris Message - time-series of Cartesian states |
| OCM  | Orbit Comprehensive Message - flexible multi-block trajectory/covariance/maneuver data |

Both KVN (plain-text `KEY = VALUE`) and XML formats are supported for all four types.

## Running tests

```bash
pytest
```
