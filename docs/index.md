# ccsds-data-messages

A Python library to read, write, and validate CCSDS Orbit Data Messages (ODM):
OEM, OMM, OPM, and OCM, in both KVN and XML formats.

It implements CCSDS 502.0-B-3. The domain models permit exactly what the spec permits
and reject exactly what the spec rejects. Every message is a Pydantic model that
validates on construction, so an instance is either fully spec-conformant or it does
not exist.

```python
from ccsds_data_messages import read, write, OEM

# Read any supported format. The format and message type are auto-detected.
msg = read("my_file.oem")
assert isinstance(msg, OEM)

# Write to a different format, inferred from the output file extension.
write(msg, "output.xml")
```

```{admonition} Disclaimer
:class: warning

This library does not guarantee that the messages it produces or parses are accurate
or fit for any operational purpose. See {doc}`disclaimer` before relying on it for
navigation, collision avoidance, or debris tracking.
```

```{toctree}
:maxdepth: 2
:caption: Contents

installation
api
design
disclaimer
changelog
```
