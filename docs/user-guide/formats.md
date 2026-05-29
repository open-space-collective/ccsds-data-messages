# Formats

The library reads and writes two CCSDS-defined serialization formats: **KVN** (Key-Value
Notation) and **XML**. Both are defined in CCSDS 502.0-B-3 §7 (KVN) and §8 (XML), and
both carry exactly the same information — format choice is a matter of tooling preference.

## KVN (Key-Value Notation)

KVN is the plain-text human-readable format. Files are typically given `.oem`, `.omm`,
`.opm`, or `.ocm` extensions.

### Structure

A KVN document is divided into blocks separated by delimiter keywords:

```
HEADER KEYWORDS
(free keyword-value pairs, one per line)

META_START
  METADATA KEYWORDS
META_STOP

DATA LINES
(free-form rows)

COVARIANCE_START   ← OEM only; omitted if no covariance block
  COVARIANCE ROWS
COVARIANCE_STOP
```

Each segment in an OEM repeats the META/DATA/COVARIANCE triple. All other message types
(OMM, OPM, OCM) have their own block structures defined in the spec.

### Formatting rules (§7.4)

- **Keywords and values** are separated by ` = `. Whitespace around `=` is insignificant.
- **Inline units** may appear in brackets after the value: `X = 1234.567 [km]`. Units are
  stripped during parsing and are not part of the field value.
- **Comments** use the `COMMENT` keyword: `COMMENT This is a comment`. Comments may appear
  only at section boundaries.
- **Blank lines** and lines beginning with `%` are ignored.

### Annotated example (OEM, two segments)

```
CCSDS_OEM_VERS = 3.0                   ← version keyword — first non-blank line (§7.3.6)
COMMENT        Tydirium approach        ← optional header comment
CREATION_DATE  = 2983-10-06T03:00:00Z  ← mandatory header fields
ORIGINATOR     = GALACTIC-EMPIRE
MESSAGE_ID     = OEM-004               ← optional

META_START                             ← segment 1 metadata block
OBJECT_NAME          = IMPERIAL SHUTTLE TYDIRIUM
OBJECT_ID            = 2983-101A
CENTER_NAME          = EARTH
REF_FRAME            = EME2000
TIME_SYSTEM          = UTC
START_TIME           = 2983-10-06T04:00:00.000Z
STOP_TIME            = 2983-10-06T04:30:00.000Z
INTERPOLATION        = HERMITE
INTERPOLATION_DEGREE = 7
META_STOP

COMMENT Ephemeris format: EPOCH X Y Z X_DOT Y_DOT Z_DOT X_DDOT Y_DDOT Z_DDOT

2983-10-06T04:00:00.000Z  1917.0   0.0   0.0  -0.000  1.599  0.128  -3.0e-09  0.0  0.0
2983-10-06T04:05:00.000Z  1857.3  474.7  38.0  -0.396  1.549  0.124  -2.9e-09 -7.5e-10 -4.2e-06

COVARIANCE_START
EPOCH = 2983-10-06T04:00:00.000Z
COV_REF_FRAME = RTN
 3.2500e-04                           ← 21 lower-triangular elements, one row at a time
 1.0100e-04  4.1100e-04
-1.5000e-05  3.0000e-05  9.2000e-05
...
COVARIANCE_STOP
```

#### Epoch format (§7.5.10)

All timestamps must be in one of two formats:

```
YYYY-MM-DDThh:mm:ss[.d+][Z]   ← calendar format  (preferred)
YYYY-DOYThh:mm:ss[.d+][Z]     ← day-of-year format
```

Examples: `2025-01-15T12:30:00`, `2025-015T12:30:00Z`, `2025-01-15T12:30:00.000`.

## XML

XML is the structured format preferred for machine-to-machine interchange. Files use the
`.xml` extension.

### Structure (§8)

XML documents start with the standard declaration, followed by a root element whose name
matches the message type (`<oem>`, `<omm>`, `<opm>`, `<ocm>`). The body is divided into
`<header>` and `<body>` elements:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<oem xmlns:xsi="..."
     xsi:noNamespaceSchemaLocation="..."
     id="CCSDS_OEM_VERS" version="3.0">

  <header>
    <CREATION_DATE>2025-01-01T00:00:00Z</CREATION_DATE>
    <ORIGINATOR>MY-AGENCY</ORIGINATOR>
  </header>

  <body>
    <segment>
      <metadata>
        <OBJECT_NAME>MY SPACECRAFT</OBJECT_NAME>
        <OBJECT_ID>2025-001A</OBJECT_ID>
        <CENTER_NAME>EARTH</CENTER_NAME>
        <REF_FRAME>EME2000</REF_FRAME>
        <TIME_SYSTEM>UTC</TIME_SYSTEM>
        <START_TIME>2025-01-01T00:00:00</START_TIME>
        <STOP_TIME>2025-01-02T00:00:00</STOP_TIME>
      </metadata>

      <data>
        <stateVector>
          <EPOCH>2025-01-01T00:00:00</EPOCH>
          <X units="km">6571.0</X>
          <Y units="km">0.0</Y>
          <Z units="km">0.0</Z>
          <X_DOT units="km/s">0.0</X_DOT>
          <Y_DOT units="km/s">7.784</Y_DOT>
          <Z_DOT units="km/s">0.0</Z_DOT>
        </stateVector>
      </data>
    </segment>
  </body>

</oem>
```

### XML keyword names

XML element names match KVN keyword strings exactly (e.g., `<OBJECT_NAME>`, `<X>`,
`<CX_X>`). This is not a coincidence — both formats use the same CCSDS-defined keyword
vocabulary, and the library stores keyword strings in exactly one place (on the domain
model's `FieldMetadata` annotations) used by both KVN and XML adapters.

### Units attributes (§8.13.6)

Numeric elements may carry a `units=""` attribute. The library writes units by default
(`WriterOptions(include_units=True)`, the default). Set `include_units=False` to omit them:

```python
from orbit_data_messages import Writer, WriterOptions
Writer.write(msg, "output.xml", options=WriterOptions(include_units=False))
```

## Format detection

When no explicit `fmt=` is passed to `Reader.read()`, format is detected in this order:

1. **File extension** — `.xml` → XML; `.oem`, `.omm`, `.opm`, `.ocm` → KVN.
2. **Content sniff** — first non-blank line starting with `<` → XML (§8.2);
   starting with `CCSDS_` → KVN (§7.3.6).
3. **Default fallback** — KVN.

Message type is detected similarly: extension first, then filename stem keyword
(`ephemeris` → OEM, `mean` → OMM, `parameter` → OPM, `comprehensive` → OCM), then
content sniff of the version keyword or XML root tag.
