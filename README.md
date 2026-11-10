# ccsds-data-messages

[![CI](https://github.com/open-space-collective/ccsds-data-messages/actions/workflows/ci.yml/badge.svg)](https://github.com/open-space-collective/ccsds-data-messages/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/ccsds-data-messages.svg)](https://pypi.org/project/ccsds-data-messages/)
[![Python versions](https://img.shields.io/pypi/pyversions/ccsds-data-messages.svg)](https://pypi.org/project/ccsds-data-messages/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A Python library to read, write, and validate CCSDS Orbit Data Messages (ODM) -
OEM, OMM, OPM, and OCM - in both KVN and XML formats.

Implements CCSDS 502.0-B-3. The domain models permit exactly what the spec permits
and reject exactly what the spec rejects.

> [!WARNING]
> **Disclaimer.** This library handles message data; it is not a source of
> authoritative orbital information. Passing validation does not mean the numbers in a
> message are accurate or safe to act on. Do not rely on it as the sole basis for any
> operational, collision-avoidance, or debris-tracking decision, and always verify
> inputs and outputs independently. The authors and Loft Orbital accept no liability for
> any resulting loss or damage. See [DISCLAIMER.md](DISCLAIMER.md) for the full notice.

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

## Validation behavior

Domain models are Pydantic models that validate on construction, so an instance is
either fully spec-conformant or it doesn't exist. Reading a file runs the same
validation as constructing a model directly - a malformed or non-conformant file
raises before you get a partially-built object back.

Unknown keywords are rejected (`extra="forbid"`), not silently dropped. Where the
spec says a field's value "should" come from a fixed set but permits ICD-agreed
alternatives (as opposed to "shall", a hard requirement), the corresponding field
accepts either the typed enum or a plain string - for example `RefFrame | str` for
`REF_FRAME`, so a parametric or non-standard frame name isn't rejected outright.

## Error handling

All library-raised exceptions inherit from `CCSDSError`:

```python
from ccsds_data_messages import (
    read,
    DetectionError,          # format or message type could not be determined
    UnsupportedAdapterError, # no reader/writer registered for the (format, type) pair
    SpecViolationError,      # content parsed but failed domain model validation
)

try:
    msg = read("ambiguous_file.txt")
except DetectionError:
    msg = read("ambiguous_file.txt", fmt="kvn", message_type="oem")
except SpecViolationError as exc:
    print(f"File does not conform to CCSDS 502.0-B-3: {exc}")
```

`ParseError` (malformed content that can't be tokenized at all, distinct from
content that parses but fails spec validation) is also part of the hierarchy.

## Writer options

`WriterOptions` controls output formatting; pass it to `write()`:

```python
from ccsds_data_messages import write, WriterOptions

# Compact KVN: no keyword-column alignment, omit spec-default-valued fields.
write(msg, "output.oem", options=WriterOptions(align_keywords=False, suppress_defaults=True))

# XML without unit attributes on numeric elements.
write(msg, "output.xml", options=WriterOptions(include_units=False))

# Override float formatting for specific keywords (Python format-spec mini-language).
write(msg, "output.oem", options=WriterOptions(float_formats={"X": " .6f", "Y": " .6f"}))
```

## Developers

Tooling is managed with [uv](https://docs.astral.sh/uv/).

### Dev container

The dev container needs only Docker on the host. It runs as your host user, mounts the repository at `/workspace` so edits are visible both ways, and mounts your `~/.gitconfig` and `~/.ssh` read-only.

```bash
make dev-image   # build the image (ccsds-data-messages:dev)
make dev         # build if needed, then open a bash shell in the container
```

To use a different Python version, pass `PYTHON_VERSION`, e.g. `make dev PYTHON_VERSION=3.12`.

### Running tests

Run the full suite (same as CI, with an 80% coverage gate):

```bash
make test        # or: uv run pytest
```

Run a single file, class, or test. Add `--no-cov` because the coverage gate applies to the whole package and fails on a partial run:

```bash
uv run pytest tests/models/test_conversions.py --no-cov
uv run pytest tests/models/test_conversions.py::TestOemToTracsSOcm --no-cov
uv run pytest tests/models/test_conversions.py::TestOemToTracsSOcm::test_cartpv_data_line_format --no-cov
uv run pytest -k "covariance" --no-cov   # tests whose name matches an expression
```

### Style

```bash
make format  # runs formatting
make lint  # checks format
```
