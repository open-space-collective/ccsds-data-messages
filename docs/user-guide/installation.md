# Installation

## Requirements

- Python 3.10 or later

## Basic install

Install the core package from PyPI:

```bash
pip install orbit-data-messages
```

The core package reads and writes all four message types (OEM, OMM, OPM, OCM) in both
KVN and XML formats. It depends only on [Pydantic v2](https://docs.pydantic.dev/latest/)
and the Python standard library.

## Optional extras

Optional extras unlock the computation layer. Install only what you need:

```bash
# NumPy backend — position/velocity arrays, covariance arrays
pip install orbit-data-messages[numpy]

# Open Space Toolkit backend — trajectory objects, interpolation
pip install orbit-data-messages[ostk]

# Both at once
pip install orbit-data-messages[numpy,ostk]
```

### What each extra enables

| Extra | Unlocks |
|---|---|
| `numpy` | `NumpyBackend` — `to_array()` / `from_numpy()`, covariance arrays |
| `ostk` | `OSTkBackend` — `to_ostk()` / `from_ostk()`, Hermite/Lagrange interpolation via OSTk |

The core package and `PurePythonBackend` (plain lists, no arrays) always work without any
extra installed. A missing optional extra raises `ImportError` with install instructions
the first time the relevant backend is imported — never at package import time.

## MkDocs documentation (development)

To build the documentation site locally:

```bash
pip install mkdocs "mkdocstrings[python]>=0.24"
mkdocs serve
```
