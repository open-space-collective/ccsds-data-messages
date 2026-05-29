# CCSDS Data Messages Package - Claude Working Plan

## How to use this document

This is both an architectural reference and a step-by-step Claude working plan.
Follow this sequence exactly:

1. **Start every Claude session** by pasting the _Context anchor_ listed for that task.
2. **Implement** only the files listed - nothing else.
3. **Peer review** by asking Claude: _"Review your output against the checklist below. List any violations."_ Do not proceed until the review passes.
4. **Then move to the next task.**

Never combine tasks. Never skip the peer review step.

---

## Overview

This package provides Python representations of the **CCSDS Orbit Data Message (ODM) standard** (CCSDS 502.0-B): the Orbit Parameter Message (OPM), Orbit Mean-Elements Message (OMM), Orbit Ephemeris Message (OEM), and Orbit Comprehensive Message (OCM).

The implementation targets **CCSDS 502.0-B-3** (February 2023). The spec is the final arbiter of any ambiguity in this codebase.

### What this package is

A faithful, complete implementation of the ODM standard - nothing more, nothing less. The domain models are the authoritative source of truth. They permit exactly what the spec permits and reject exactly what the spec rejects. No convenience relaxations, no undocumented extensions.

If the spec says a field is mandatory, it is mandatory here. If the spec says a value must lie within a range, that range is enforced. If the spec is silent on a constraint, so is this package. Divergence from the spec is always a bug, never a feature.

### What this package is not

An orbital mechanics engine. It does not propagate orbits, evaluate force models, or make any physical claim about the validity of the data it holds. The computation layer provides interpolation, resampling, and interoperability with libraries that do — but the physics live in those libraries, not here. This package reads, writes, validates, and converts - correctly and completely.

### Who it is for

**Astrodynamicists** who need confidence that what goes in and what comes out is exactly what the standard describes - no silent truncations, no unit surprises, no format ambiguity. The domain models speak the language of the spec: field names match the standard's keywords, units are documented at every field, and validation messages cite the relevant section numbers.

**Developers** who need to move orbit data between systems without becoming ODM experts. `Reader.read("file.oem")` returns a validated Python object. `Writer.write(msg, "output.xml")` writes a conformant file. The formats, the block structure, the keyword syntax - all invisible unless you want to see them.

### Design priorities, in order

1. **Correctness** - the domain models never permit invalid ODM data.
2. **Completeness** - every field, every message type, both KVN and XML formats.
3. **Developer experience** - intuitive API, good errors (and messages), no surprises.

When these conflict, correctness wins.

### On keyword names and field identity

The CCSDS standard defines each field with both a semantic meaning and a keyword name (`OBJECT_NAME`, `CCSDS_OEM_VERS`, `REF_FRAME`, etc.). These are inseparable: the keyword is not an I/O accident - it is part of how the spec names the concept, in the same way that a unit or a valid range is part of the field's definition.

For this reason, **keyword names and units live on the domain models** as metadata annotations (`FieldMetadata(keyword=..., units=...)`), and **block delimiters live on the nested classes (or fields) that represent those blocks** (`Delineation("META_START", "META_STOP")`). This is self-description, not format coupling.

The line between domain and adapter is drawn here:

- **Domain models own:** keyword name, unit, valid range, whether a field is mandatory - the *identity* of a field as defined by the spec.
- **Adapters own:** parsing logic, string-to-Python conversion, block sequencing, file I/O - the *mechanics* of reading and writing.

A generic KVN adapter can therefore introspect the model's metadata rather than hardcoding keyword-to-field mappings. Adding a new field to the domain model makes it automatically serializable - no adapter change required. This also means the keyword strings exist in exactly one place: on the field itself, not duplicated across every adapter that touches it.

---

## Part 1 - Architectural Reference

Read this once. Paste relevant sections as context anchors in each task.

### Guiding Principles

- **Domain models are the interchange format.** Pydantic models use only plain Python scalars (`float`, `str`, `int`). Zero non-Pydantic dependencies. They validate, they serialize, they are the truth.
- **Domain models own their identity; adapters own parsing mechanics.** Keyword names, units, and block delimiters are part of the spec's definition of each field - they live on the domain model as metadata (`FieldMetadata(keyword=..., units=...)`, `Delineation(...)`). Adapters introspect that metadata rather than hardcoding mappings. What adapters own exclusively is parsing logic: string-to-Python conversion, block sequencing, file I/O.
- **Adapters work directly against the spec.** Every parser, serializer, and format-detection rule cites the relevant section of CCSDS 502.0-B-3. If spec and code disagree, the spec wins.
- **The facade hides the plumbing.** Users call `Reader.read("file.oem")` and get back a domain model. Format detection, adapter selection, and parsing are invisible.
- **`CCSDSDataMessage` is abstract - never instantiated directly.** It exists only as a type-hint base. Concrete message types are the only valid instances.
- **Views are the computation API.** A view wraps a domain model and adds computation methods. Backends supply the math.
- **Backends are math library adapters.** Each backend translates domain model fields into the types and operations of one library. Adding a new backend never touches domain models.
- **Backends own both directions.** A backend that converts domain > external also converts external > domain. Both live in the same class.
- **`from_` classmethods keep the domain pure.** They are one-liner delegates to a backend. The backend produces plain Python values; Pydantic construction validates them. Zero logic in the domain model itself.
- **Explicit over ambient.** The primary API is `Ephemeris*View(data, backend=NumpyBackend())`. A context manager is a convenience layer only.
- **Optional dependencies stay optional.** Numpy, OSTk, and astropy are extras. The package works without any of them via a pure-Python backend.

### Package layout

```
ccsds/
├── models/
│   ├── base.py          # CCSDSDataMessage ABC - never instantiated
│   ├── oem.py           # OEM(CCSDSDataMessage, BaseModel)
│   ├── omm.py
│   ├── opm.py
│   └── ocm.py
│
├── io/
│   ├── ports.py         # MessageReaderPort, MessageWriterPort protocols
│   ├── reader.py        # Reader facade
│   ├── writer.py        # Writer facade
│   ├── registry.py      # (format, msg_type) > adapter class, lazy imports
│   ├── detection.py     # format + message-type sniffing
│   ├── kvn/
│   │   ├── parser.py    # KVN tokenizer - no domain types
│   │   ├── oem_reader.py
│   │   ├── oem_writer.py
│   │   └── ...          # one reader + one writer per message type
│   └── xml/
│       ├── parser.py
│       ├── oem_reader.py
│       ├── oem_writer.py
│       └── ...
│
└── compute/
    ├── backends/
    │   ├── base.py      # Ephemeris*Backend, Covariance*Backend protocols
    │   ├── pure.py      # PurePythonBackend - no optional deps
    │   ├── numpy_.py    # NumpyBackend
    │   └── ostk_.py     # OSTkBackend
    ├── views.py         # Ephemeris*View, State*View, Covariance*View
    ├── factories.py     # ephemeris*_from_propagator, etc.
    └── registry.py      # backend("numpy") + using_backend() context manager
```

### Dependency rule

```
io/adapters  >  models/  <  compute/views
               (domain)
```

IO adapters import from `models/`. Compute views import from `models/`. `models/` imports from neither. This is the only allowed direction.

### Responsibility table

| Concern | Lives in |
|---|---|
| Field names, types, validators, invariants | `models/` |
| Spec keyword names (`OBJECT_NAME`, `CCSDS_OEM_VERS`, …) | `models/` - as `FieldMetadata(keyword=...)` |
| Spec units (`km`, `km/s`, `km**2`, …) | `models/` - as `FieldMetadata(units=...)` |
| Block delimiters (`META_START/STOP`, `COVARIANCE_START/STOP`, …) | `models/` - as `Delineation(...)` on nested classes or fields |
| KVN parsing logic - tokenization, block splitting, string>Python | `io/kvn/parser.py` |
| KVN serialization logic - Python>string, ordering, formatting | `io/kvn/` adapters (introspect model metadata) |
| XML parsing and serialization logic | `io/xml/` adapters (introspect model metadata) |
| CCSDS date string parsing (§7.5.10) | `io/` adapters |
| File extension > format inference | `io/detection.py` |
| Message-type detection from file content | `io/detection.py` |
| Adapter selection | `io/registry.py` |
| User-facing read/write API | `io/reader.py`, `io/writer.py` |
| Domain <> numpy conversion | `compute/backends/numpy_.py` |
| Domain <> OSTk conversion | `compute/backends/ostk_.py` |
| Interpolation, resampling | `compute/backends/` + `compute/views.py` |

---

## Part 2 - Task Breakdown

---

### Task 0 - `OrbitComprehensiveMessage`

**Files**: `core/ocm.py`

**Context anchor - paste this at the start of the Claude session:**

> We are building a CCSDS orbit data message package. The domain models are Pydantic v2 `BaseModel` subclasses. Make sure that:
> - `OCM` / `OrbitComprehensiveMessage` is correct
> - `OCM` / `OrbitComprehensiveMessage` is complete
> - `OCM` / `OrbitComprehensiveMessage` follows the patterns established in the other message models
> 
> Implement/adjust `core/ocm.py` only.

**Peer-review checklist - ask Claude to verify each point before proceeding:**

- [ ] `OrbitComprehensiveMessage` os correct, complete, and to spec

### Task 1 - `CCSDSDataMessage` abstract base

**Files:** `models/base.py`

**Context anchor - paste this at the start of the Claude session:**

> We are building a CCSDS orbit data message package. The domain models are Pydantic v2 `BaseModel` subclasses. We need an abstract base class `CCSDSDataMessage` that:
> - Cannot be instantiated directly (raises `TypeError`)
> - Has no fields, no validators, no Pydantic machinery
> - Is used only as a type hint: `def read(...) -> CCSDSDataMessage`
> - Concrete subclasses will do `class OEM(CCSDSDataMessage, BaseModel): ...`
>
> Implement `models/base.py` only.

**Peer-review checklist - ask Claude to verify each point before proceeding:**

- [ ] `CCSDSDataMessage()` raises `TypeError` - confirmed with a `pytest.raises` snippet or inline assert
- [ ] `CCSDSDataMessage` imports nothing beyond `abc`
- [ ] No Pydantic imports anywhere in `base.py`
- [ ] `class OEM(CCSDSDataMessage, BaseModel): pass` resolves without MRO error (Claude should reason through the MRO explicitly)
- [ ] No fields, no `model_config`, no validators on the base

---

### Task 2 - Wire `OEM` into `CCSDSDataMessage`

**Files:** `models/oem.py` (modify existing)

**Context anchor:**

> `models/base.py` now defines `CCSDSDataMessage(ABC)` with no fields and no Pydantic machinery. Concrete models inherit `class OEM(CCSDSDataMessage, BaseModel)`.
>
> Modify `models/oem.py` to add `CCSDSDataMessage` as a base. Make no other changes - no new fields, no new validators, no computation shortcuts yet (those come later). The existing OEM model and all its nested classes must be fully preserved.

**Peer-review checklist:**

- [ ] Only the class declaration line changed - diff is one line per top-level class
- [ ] All existing validators, fields, and nested classes are intact
- [ ] `OEM()` (with valid args) still constructs successfully
- [ ] `CCSDSDataMessage()` still raises `TypeError`
- [ ] `isinstance(oem_instance, CCSDSDataMessage)` returns `True`

---

### Task 3 - I/O ports

**Files:** `io/ports.py`

**Context anchor:**

> We are adding a ports-and-adapters I/O layer. The ports are abstract Protocol classes - they describe what any adapter must provide, with no reference to format details or concrete implementations.
>
> `CCSDSDataMessage` (from `models/base.py`) is the only domain type the ports need to know about.
>
> Implement `io/ports.py` with `MessageReaderPort` and `MessageWriterPort`.

**Peer-review checklist:**

- [ ] Both are `typing.Protocol` (not ABC, not concrete class)
- [ ] `MessageReaderPort.read(path: Path) -> CCSDSDataMessage` - exact signature
- [ ] `MessageWriterPort.write(message: CCSDSDataMessage, path: Path) -> None` - exact signature
- [ ] No imports from `io/kvn/`, `io/xml/`, or `compute/`
- [ ] No format-specific logic, no `open()`, no file I/O of any kind

---

### Task 4 - KVN low-level parser

**Files:** `io/kvn/parser.py`

**Spec sections to have open while working:** §7.3 (KVN structure), §7.4 (KVN formatting rules), §7.8 (comment and keyword rules).

**Context anchor:**

> We are implementing a low-level KVN tokenizer strictly according to CCSDS 502.0-B-3 §7.3–7.4.
>
> KVN structure (from the spec):
> - Header: free keyword-value pairs, one per line, `KEYWORD = value` (§7.3.3)
> - Metadata block: delimited by `META_START` / `META_STOP` (§7.3.4)
> - Data block: free-form lines following the metadata block (§7.3.5)
> - Covariance block (OEM only): delimited by `COVARIANCE_START` / `COVARIANCE_STOP` (§7.3.6)
> - Comments: `COMMENT <text>` keyword, may appear at section boundaries only (§7.8)
> - Inline units: `KEYWORD = value [unit]` - the `[unit]` suffix must be stripped (§7.4.6)
> - Blank lines and lines beginning with `%` are ignored (§7.4.2)
>
> The adapter - not this parser - is responsible for knowing which keywords belong to which message type. The parser produces raw dicts only.
>
> **Important:** keyword names live on the domain model as `FieldMetadata(keyword=...)`. The parser does not need to know them - it tokenizes any valid KVN text generically.
>
> Implement `io/kvn/parser.py`:
> - `parse_kvn(text: str) -> dict` - full document > structured dict
> - `split_blocks(raw: dict) -> list[dict]` - separate header, segments, meta/data/covariance sub-dicts

**Peer-review checklist:**

- [ ] Every non-trivial parsing rule has a comment citing the spec section it implements (e.g. `# §7.4.6 - strip inline unit`)
- [ ] No imports from `models/`, `compute/`, or any other `io/` submodule
- [ ] Returns only plain Python types: `str`, `float`, `int`, `list`, `dict`
- [ ] Handles: inline `[unit]` stripping (§7.4.6), `COMMENT` lines accumulated as list (§7.8), block delimiters `META_START/STOP` and `COVARIANCE_START/STOP`, blank lines and `%` comment lines ignored (§7.4.2)
- [ ] Data lines (epoch + floats) are returned as raw strings - not parsed; that is the adapter's job
- [ ] Has at least one unit test using a minimal KVN fixture taken directly from the spec examples

---

### Task 5 - First KVN adapter: OEM reader

**Files:** `io/kvn/oem_reader.py`

**Spec sections to have open while working:** §5.2 (OEM structure), §7.3–7.4 (KVN rules), §7.5.10 (date/time formats), §7.7.2 (units).

**Context anchor:**

> `io/kvn/parser.py` tokenizes KVN text into plain dicts. Now we need the first message-specific adapter: `KVNOEMReader`, which maps those dicts into a validated `OEM` domain model.
>
> **Keyword names are not hardcoded here.** The `OEM` domain model carries `FieldMetadata(keyword=...)` on every field. The adapter introspects these annotations to map tokenized KVN keys to model fields generically. This means keyword strings exist in exactly one place: the domain model.
>
> Block delimiters (`META_START/STOP`, `COVARIANCE_START/STOP`) are carried on the nested classes as `Delineation(...)`. The adapter reads them from the model rather than hardcoding them.
>
> Data lines follow the spec exactly (§5.2.4.1):
> `epoch x y z x_dot y_dot z_dot [x_ddot y_ddot z_ddot]`
> Accelerations are present if and only if 10 whitespace-separated tokens appear on the line.
>
> Date/time strings follow §7.5.10 - the adapter parses them; the domain model stores them as validated strings.
>
> Implement `io/kvn/oem_reader.py` with class `KVNOEMReader` satisfying `MessageReaderPort`.

**Peer-review checklist:**

- [ ] Implements `MessageReaderPort` structurally (signature must match exactly)
- [ ] Calls `parse_kvn` / `split_blocks` from `io/kvn/parser.py` - does not re-implement tokenization
- [ ] Reads keyword names from `FieldMetadata` annotations on the `OEM` model - does not hardcode `"OBJECT_NAME"` etc. as string literals in the adapter
- [ ] Reads block delimiters from `Delineation` annotations on nested classes - does not hardcode `"META_START"` etc.
- [ ] Data line parsing follows §5.2.4.1 exactly - comment cites the section
- [ ] Returns a fully constructed `OEM` instance - Pydantic validation fires on construction
- [ ] No try/except that swallows Pydantic `ValidationError` - let it propagate
- [ ] Handles optional fields (`MESSAGE_ID`, `COMMENT`, `USEABLE_START_TIME`, covariance block) per the spec's optionality rules
- [ ] Passes a round-trip test using the example OEM from the spec (or the uploaded PDF fixture)

---

### Task 6 - Format and message-type detection

**Files:** `io/detection.py`

**Spec sections to have open while working:** §7.3.2 (KVN version keyword line is always first), §7.4.3 (XML document structure).

**Context anchor:**

> We need to auto-detect (a) whether a file is KVN or XML, and (b) which CCSDS message type it contains, so `Reader.read("file.oem")` can work without explicit arguments.
>
> Detection priority (most reliable to least [might not be the order listed below]):
> 1. File extension (`.oem`, `.omm`, `.opm`, `.ocm` > type; `.xml` > format)
> 2. Filename stem keywords (`ephemeris`, `mean`, `parameter`, `comprehensive`)
> 3. Content sniff: XML files begin with `<` (§7.4.3); KVN files have the version keyword (`CCSDS_OEM_VERS`, `CCSDS_OMM_VERS`, etc.) as the first non-blank, non-comment line (§7.3.2)
>
> Implement `io/detection.py` with:
> - `detect_format(path: Path) -> Literal["kvn", "xml"]`
> - `detect_message_type(path: Path, fmt: str) -> Literal["oem", "omm", "opm", "ocm"]`

**Peer-review checklist:**

- [ ] Content-sniff rules cite their spec section in a comment
- [ ] No imports from `models/`, `compute/`, or any adapter module
- [ ] Detection is pure - no side effects beyond reading the file
- [ ] `detect_format` never raises on a valid file; falls back to content sniff
- [ ] `detect_message_type` raises `ValueError` with a clear message if type cannot be determined - no silent defaults
- [ ] KVN version keyword detection reads only the minimum necessary lines (stops at first non-blank, non-comment line per §7.3.2)
- [ ] Unit tests cover: `.oem` extension, `.xml` extension, ambiguous `.txt` with KVN content, ambiguous `.txt` with XML content

---

### Task 7 - Adapter registry

**Files:** `io/registry.py`

**Context anchor:**

> We need a registry that maps `(format, message_type)` tuples to the correct reader/writer adapter class, using lazy imports so that `import ccsds.io` does not load all adapter modules.
>
> Implement `io/registry.py` with:
> - `get_reader(fmt: str, msg_type: str) -> MessageReaderPort`
> - `get_writer(fmt: str, msg_type: str) -> MessageWriterPort`
>
> Use string references for lazy import: `"ccsds.io.kvn.oem_reader:KVNOEMReader"`. Import and instantiate only when called.

**Peer-review checklist:**

- [ ] Adapter classes are referenced as strings - no top-level `from ccsds.io.kvn import ...`
- [ ] `get_reader` / `get_writer` raise `ValueError` with available options listed if the key is not registered
- [ ] Adding a new adapter requires only one new line in the registry dict
- [ ] `import ccsds.io.registry` does not trigger any adapter module imports (verify by checking `sys.modules` in a test)

---

### Task 8 - Reader and Writer facades

**Files:** `io/reader.py`, `io/writer.py`

**Context anchor:**

> The reader and writer facades are the only thing users interact with directly (in the preferred use case; they can directly import and use type readers and writers of course). They:
> - Accept a path (and optional overrides for format and message type)
> - Call `detect_format` / `detect_message_type` from `io/detection.py`
> - Look up the right adapter via `io/registry.py`
> - Delegate reading/writing entirely to the adapter
>
> `Reader.read()` returns `CCSDSDataMessage`. `Writer.write()` infers format from the output extension, falling back to KVN.
>
> Implement `io/reader.py` and `io/writer.py`.

**Peer-review checklist:**

- [ ] `Reader` and `Writer` contain zero parsing logic - they only orchestrate
- [ ] `Reader.read(path)` with no overrides auto-detects both format and type
- [ ] `Reader.read(path, fmt="kvn", message_type="oem")` bypasses detection entirely
- [ ] `Writer.write(msg, path)` infers format from extension; `fmt=` overrides it
- [ ] Both accept `str | Path` for the path argument
- [ ] Return type annotation of `Reader.read` is `CCSDSDataMessage`, not a concrete type
- [ ] End-to-end test: read a KVN OEM file > write to XML > read back > compare field values

---

### Task 9 - Remaining KVN adapters

**Files:** `io/kvn/oem_writer.py`, `io/kvn/omm_reader.py`, `io/kvn/omm_writer.py`, etc.
_(one Claude session per reader+writer pair)_

**Spec sections to have open while working:** the message-type-specific section (§4 for OPM, §5 for OMM, §6 for OEM, §7 for OCM) plus §7.3–7.4 for KVN rules. The writer must produce keywords and blocks in exactly the order the spec defines.

**Context anchor (per session):**

> `io/kvn/oem_reader.py` is the reference implementation. Follow exactly the same pattern for `[OMM / OPM / OCM]`.
>
> Key principles carried forward:
> - Read keyword names from `FieldMetadata(keyword=...)` annotations on the domain model - do not hardcode keyword strings in the adapter
> - Read block delimiters from `Delineation(...)` annotations on nested classes
> - All parsing rules cite the relevant spec section in a comment (always double check with the specs though)
>
> For the writer: output keywords and blocks in exactly the order the spec defines for this message type. The writer is the exact inverse of the reader - it introspects the same model metadata to produce the keyword strings, in the correct order.
>
> Implement `io/kvn/[message_type]_reader.py` and `io/kvn/[message_type]_writer.py`.

**Peer-review checklist (per pair):**

- [ ] Keyword names are read from `FieldMetadata` annotations - no hardcoded keyword strings in the adapter
- [ ] Block delimiters are read from `Delineation` annotations - not hardcoded
- [ ] Writer produces keywords in the order the spec mandates - comment cites the spec table (always double check with the specs though)
- [ ] Writer output, when re-parsed by the reader, produces an equal domain model (`==`)
- [ ] Optional fields are omitted from output when `None` (not written as empty strings)
- [ ] Every non-trivial rule cites its spec section in a comment (always double check with the specs though)
- [ ] Register the new adapter pair in `io/registry.py` - confirm with a `get_reader("kvn", "[type]")` call in a test

---

### Task 10 - XML adapters (OEM first, then remaining)

**Files:** `io/xml/parser.py`, `io/xml/oem_reader.py`, `io/xml/oem_writer.py`
_(same pattern as Tasks 4–5 and 9, then repeated for each remaining message type)_

**Spec sections to have open while working:** §7.4 (XML document structure and formatting rules), plus the message-type-specific section for the type being implemented.

**Context anchor:**

> We now add XML format support. The design mirrors the KVN layer exactly:
>
> - `io/xml/parser.py` wraps `xml.etree.ElementTree` and provides low-level helpers (find element text, parse attributes, handle namespaces). It produces plain dicts - no domain types.
> - `io/xml/oem_reader.py` maps XML elements to OEM domain model fields.
>
> **Key principle:** XML tag names are not hardcoded in the adapter. The `OEM` domain model carries `FieldMetadata(keyword=...)` - the same keyword string used for KVN is also the XML element name (the CCSDS spec defines them to match). The adapter introspects these annotations exactly as the KVN adapter does.
>
> Block delimiters (`META_START/STOP` etc.) become wrapping XML elements in the XML format - the `Delineation` annotation on the nested class tells the adapter the element name.
>
> All parsing rules cite their spec section (§7.4.x) in a comment.

**Peer-review checklist:**

- [ ] `io/xml/parser.py` imports no domain or adapter modules
- [ ] XML element names are read from `FieldMetadata(keyword=...)` - not hardcoded in the adapter
- [ ] Namespace handling is contained in `parser.py`, not scattered across adapters
- [ ] Every non-trivial rule cites its spec section in a comment (always double check with the specs though)
- [ ] Round-trip test: OEM domain model > XML writer > XML reader > field equality
- [ ] The same `FieldMetadata(keyword=...)` value is used consistently for both KVN keyword and XML element name (confirm by inspection against the spec)

---

### Task 11 - Compute backend protocols

**Files:** `compute/backends/base.py`

**Context anchor:**

> We are adding a computation layer. Backends are classes that translate between domain model types and external math library types (numpy, OSTk, etc.). Each backend owns **both directions**: domain > external and external > domain.
>
> Define Protocol classes for `EphemerisBackend` and `CovarianceBackend` in `compute/backends/base.py` (check if more are needed based on the users/use cases/spec). No implementation - protocols only.
>
> Guiding principles:
> - `from_` methods must return fully constructed domain model instances (Pydantic validation fires)
> - `to_` methods return `Any` - the backend decides the external type
> - The protocol must not import numpy, OSTk, or any optional dependency

**Peer-review checklist:**

- [ ] Both are `typing.Protocol`
- [ ] `EphemerisBackend` has: `position`, `velocity`, `acceleration`, `parse_epoch`, `to_array`, `trajectory_from_ephemeris`, `interpolate`, `steps`, `ephemeris_data_from_array`, `ephemeris_data_from_trajectory`, `state_to_line`
- [ ] `CovarianceBackend` has: `covariance_to_array`, `covariance_from_array`
- [ ] Return types for `from_` methods are the concrete domain model classes (not `Any`)
- [ ] No optional dependency imports anywhere in this file

---

### Task 12 - `PurePythonBackend`

**Files:** `compute/backends/pure.py`

**Context anchor:**

> The pure-Python backend must work with zero optional dependencies. It uses Python stdlib types only, e.g.: `list`, `tuple`, `datetime`.
>
> This backend unblocks all tests - every test that needs a backend can use this one without installing numpy or OSTk.
>
> It does not need to implement interpolation or trajectory construction - those can raise `NotImplementedError` with a clear message. Position/velocity accessors and `from_array` / `to_array` (returning plain lists) must be fully implemented.

**Peer-review checklist:**

- [ ] Zero imports outside stdlib + `ccsds.models`
- [ ] `position(line)` returns `[line.x, line.y, line.z]` (plain list)
- [ ] `to_array(data)` returns `list[list[float]]`
- [ ] `ephemeris_data_from_array(arr, epochs)` constructs and returns a valid `EphemerisData`
- [ ] Methods that are genuinely not implementable without a library raise `NotImplementedError` with a message naming the required extra
- [ ] Satisfies `EphemerisBackend` protocol structurally

---

### Task 13 - Views

**Files:** `compute/views.py`

**Context anchor:**

> Views bind a domain model to a backend. They are lightweight wrappers - they own no data, they copy nothing. The domain model is unchanged.
>
> Three views needed (check if more are needed based on the users/use cases/spec):
> - `Ephemeris*View(data: EphemerisData, backend: EphemerisBackend)` - iterable over `StateView`; callable for interpolation; `.to_numpy()`, `.to_ostk()` shortcuts
> - `StateView(line: EphemerisDataLine, backend: EphemerisBackend)` - `.epoch`, `.position`, `.velocity`, `.acceleration` properties
> - `CovarianceView(cov: CovarianceMatrix, backend: CovarianceBackend)` - iterable over matrices; `.to_numpy()`
>
> Views must not import any backend directly at module load time - only inside the `to_numpy()` / `to_ostk()` shortcut methods.

**Peer-review checklist:**

- [ ] Views store a reference to the domain model and backend - they do not copy data
- [ ] `Ephemeris*View.__iter__` yields `StateView` instances, one per data line
- [ ] `Ephemeris*View.__call__(epoch)` delegates to `backend.interpolate`
- [ ] `StateView` properties delegate to the backend - no computation in the view itself
- [ ] `to_numpy()` does a deferred `from .backends.numpy_ import NumpyBackend` - not at module level
- [ ] Removing all `to_numpy()` / `to_ostk()` methods leaves the view fully functional

---

### Task 14 - `NumpyBackend`

**Files:** `compute/backends/numpy_.py`

**Context anchor:**

> Implement the full NumpyBackend, satisfying `EphemerisBackend` and `CovarianceBackend`, etc.
>
> Both directions must be implemented, e.g.:
> - `to_array(data)` > `np.ndarray` shape `(N, 6)` or `(N, 9)`
> - `ephemeris_data_from_array(arr, epochs)` > `EphemerisData` (Pydantic validation fires)
> - `covariance_to_array(cov)` > `np.ndarray` shape `(N, 6, 6)`
> - `covariance_from_array(arr, epochs, cov_ref_frame=None)` > `CovarianceMatrix`
>
> Guard the numpy import: raise `ImportError` with install instructions if numpy is not available.

**Peer-review checklist:**

- [ ] `import numpy as np` is inside a try/except at module top with a clear `ImportError` message
- [ ] `to_array` returns shape `(N, 6)` when no accelerations, `(N, 9)` when accelerations present - not always one or the other
- [ ] `ephemeris_data_from_array` converts to `float` (not numpy scalar) before passing to domain model
- [ ] `covariance_from_array` maps `arr[i, r, c]` to the correct lower-triangle field names
- [ ] Round-trip test: `EphemerisData` > `to_array` > `ephemeris_data_from_array` > field equality

---

### Task 15 - Factories

**Files:** `compute/factories.py`

**Context anchor:**

> Factories construct domain models from dynamic sources (propagators, generators). They are standalone functions, not classmethods on domain models.
>
> Implement `ephemeris_from_propagator(propagator, start, stop, timestep_seconds, backend)` > `EphemerisData`, etc..
>
> The propagator is any callable that accepts whatever type `backend.parse_epoch` returns and produces a state the backend can convert via `state_to_line`.

**Peer-review checklist:**

- [ ] `backend` parameter defaults to `PurePythonBackend()` - factory always works without optional deps
- [ ] Returns a plain `EphemerisData` - not a view, not a numpy array
- [ ] Does not import numpy, OSTk, or any backend at module level
- [ ] The resulting `EphemerisData` passes its own `check_epochs_ordered` validator

---

### Task 16 - Compute registry and context manager

**Files:** `compute/registry.py`

**Context anchor:**

> The compute registry provides:
> - `backend(name: str)` > instantiated backend (e.g. `backend("numpy")` > `NumpyBackend()`)
> - `using_backend(name)` context manager - thread-local stack, explicitly documented as not async-safe
> - `current_backend()` > top of stack, or `PurePythonBackend()` if stack is empty
>
> The context manager is a convenience layer. The primary API is always explicit: `Ephemeris*View(data, backend=NumpyBackend())`.

**Peer-review checklist:**

- [ ] Backend classes are lazily imported inside `backend()` - not at module level
- [ ] `using_backend` docstring explicitly states: "thread-local; not safe for asyncio"
- [ ] `current_backend()` never raises - returns `PurePythonBackend()` as default
- [ ] Nesting `using_backend` contexts works correctly (inner overrides outer, outer restored on exit)

---

### Task 17 - `OSTkBackend`

**Files:** `compute/backends/ostk_.py`

**Context anchor:**

> Implement `OSTkBackend`, satisfying `EphemerisBackend` (etc.). Both directions, e.g.:
> - `trajectory_from_ephemeris(data)` > OSTk `Trajectory`
> - `ephemeris_data_from_trajectory(trajectory)` > `EphemerisData`
>
> Check if the backend protocol and views are sufficient for the necessary OSTk implementation.
> Also check all types that OSTk offers to decide the best implementation; OSTk Python API docs:
> - https://open-space-collective.github.io/open-space-toolkit-astrodynamics/_build/html/python.html
> - https://open-space-collective.github.io/open-space-toolkit-core/_build/html/python.html
> - https://open-space-collective.github.io/open-space-toolkit-mathematics/_build/html/python.html
> - https://open-space-collective.github.io/open-space-toolkit-physics/_build/html/python.html
>
> Unit conversion: OEM uses km and km/s; OSTk uses metres and m/s. All conversion lives in this file.
>
> Guard the OSTk import with a clear `ImportError` message.

**Peer-review checklist:**

- [ ] All unit conversions (km <> m) are explicit and in one place
- [ ] `ephemeris_data_from_trajectory` converts OSTk instants to CCSDS epoch strings before passing to domain model
- [ ] OSTk import is guarded; error message names the install extra
- [ ] `position(line)` returns an OSTk `Position` object (not a plain list)
- [ ] Round-trip test: `EphemerisData` > `trajectory_from_ephemeris` > `ephemeris_data_from_trajectory` > field equality within floating-point tolerance

---

### Task 18 - Domain model ergonomic shortcuts

**Files:** `models/oem.py` (and equivalent for OMM, OPM, OCM)

**Context anchor:**

> The final step adds import-guarded `to_` and `from_` shortcut methods to the domain model classes. These are one-line delegates - they contain zero logic. All logic lives in the backend.
>
> Rules:
> - Every import is deferred inside the method body
> - `from_` classmethods delegate to a backend and return the result of normal Pydantic construction - validation fires
> - Removing all these methods must leave the domain model fully functional
>
> Add to `OEM.Segment.EphemerisData`:
> - `to_numpy(self)`, `to_ostk(self)`
> - `from_numpy(cls, arr, epochs)`, `from_ostk(cls, trajectory)`
>
> Add to `OEM.Segment.CovarianceMatrix`:
> - `to_numpy(self)`
> - `from_numpy(cls, arr, epochs, cov_ref_frame=None)`
>
> Add any other necessary or missing ones.

**Peer-review checklist:**

- [ ] Every method body is a single `from ... import ...; return Backend().method(self)` or equivalent - no logic
- [ ] No import at module level - all deferred inside method bodies
- [ ] `from_` methods return a domain model instance, not a backend type
- [ ] Deleting all shortcut methods: the file still imports cleanly, `OEM(...)` still constructs, all validators still fire
- [ ] `OEM.Segment.EphemerisData.from_numpy(arr, epochs)` produces an instance that passes `check_epochs_ordered`

---

## Part 3 - Reference: Usage Examples

### Reading and writing

```python
from ccsds.io import Reader, Writer
from ccsds.models.oem import OEM

msg = Reader.read("my_file.oem")                              # auto-detect
msg = Reader.read("data.txt", fmt="kvn", message_type="oem") # explicit
assert isinstance(msg, OEM)

Writer.write(msg, "output.xml")          # XML inferred from extension
Writer.write(msg, "output.kvn", fmt="kvn")
```

### Computation - explicit backend

```python
from ccsds.compute.views import Ephemeris*View
from ccsds.compute.backends.numpy_ import NumpyBackend

view = Ephemeris*View(segment.ephemeris_data, backend=NumpyBackend())
for state in view:
    print(state.epoch, state.position, state.velocity)

arr = view.to_numpy()        # (N, 6) ndarray
sampled = view(some_epoch)   # interpolated
```

### Conversion shortcuts - "to"

```python
arr  = segment.ephemeris_data.to_numpy()   # (N, 6)
traj = segment.ephemeris_data.to_ostk()
cov  = segment.covariance_matrix.to_numpy() # (N, 6, 6)
```

### Conversion shortcuts - "from"

```python
ephem = OEM.Segment.EphemerisData.from_numpy(arr, epochs)
ephem = OEM.Segment.EphemerisData.from_ostk(ostk_trajectory)
cov   = OEM.Segment.CovarianceMatrix.from_numpy(cov_arr, epochs)
# All return fully validated domain models
```

### Context manager (convenience only)

```python
from ccsds.compute.registry import using_backend

with using_backend("ostk") as b:
    view = Ephemeris*View(segment.ephemeris_data, backend=b)
```

### Factory

```python
from ccsds.compute.factories import ephemeris_from_propagator
from ccsds.compute.backends.ostk_ import OSTkBackend

ephem = ephemeris_from_propagator(
    propagator=my_propagator,
    start="2025-01-01T00:00:00Z",
    stop="2025-01-02T00:00:00Z",
    timestep_seconds=60.0,
    backend=OSTkBackend(),
)
segment = OEM.Segment(metadata=my_metadata, ephemeris_data=ephem)
```

---

## Part 4 - Decision Log

| Decision | Rationale |
|---|---|
| `CCSDSDataMessage` is a plain ABC, no Pydantic | Single type-hint target; `TypeError` on direct construction; no MRO complexity from Pydantic internals |
| Domain models use plain Python scalars only | Zero mandatory external deps; Pydantic models are the interchange format, not a computation API |
| Keyword names and units live on domain models as `FieldMetadata` (Option A) | The CCSDS keyword (`OBJECT_NAME`, `REF_FRAME`, …) is part of the field's identity as defined by the spec - inseparable from its type and unit. Living on the model means the string exists in exactly one place; adapters introspect it rather than duplicating it. Adding a new field makes it automatically serializable. |
| Block delimiters live on nested classes as `Delineation` | Same reasoning as keyword names - `META_START/STOP` is the spec's name for the metadata block, not an I/O accident |
| Adapters introspect model metadata; they do not hardcode keyword strings | Keyword strings exist in one place; drift between model and adapter is structurally impossible |
| Adapters work directly against the spec; every rule cites a section number | The spec is the final arbiter. Citing sections in comments makes future spec-version upgrades auditable and keeps implementation honest |
| Low-level `parser.py` is separate from message-specific readers | KVN/XML tokenization is shared across all message types; semantic mapping is per-type |
| Format and type detection is its own module | Changes independently of parsing; easy to extend |
| `Reader` / `Writer` are static-method classes | Discoverable, groupable, subclassable; cleaner than bare module functions |
| Registry uses lazy string references | `import ccsds.io` has no side effects; adapters load on demand |
| Views wrap domain models, never extend them | Backends can be added without touching domain or re-validating data |
| Context manager is secondary to explicit `backend=` | Thread-local globals break asyncio; explicit is unambiguous |
| Factories are standalone functions, not classmethods | Construction from external sources is not a domain concern |
| Each backend is a plain class, not a singleton | Configurable per-instance (interpolation degree, frame, etc.) |
| Backends own both directions of conversion | The knowledge needed to convert *to* a type is the same knowledge needed to convert *from* it; keeping both in one class avoids split responsibility |
| `from_` classmethods keep the domain pure | One-line delegates; backends produce plain Python values; Pydantic validation fires on construction |
| Optional deps guarded inside method / module bodies | `import ccsds` never fails regardless of what is installed |
