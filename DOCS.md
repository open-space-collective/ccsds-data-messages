# Google-Style Docstrings and MkDocs Site
 
You are adding Google-style docstrings to a CCSDS ODM library and scaffolding a MkDocs documentation site. The library implements the CCSDS 502.0-B-3 Orbit Data Message standard (OPM, OMM, OEM, OCM) in both KVN and XML formats, with a compute layer for views, backends, and factories.
 
**Two goals, in order:**
1. Add Google-style docstrings to every module, class, method, and function in the codebase.
2. Scaffold a MkDocs site that surfaces only the public API to users, while keeping internal module docs available for maintainers via a separate nav section.
Do not modify any logic, signatures, validators, or behaviour. Docstrings only — no other changes.
 
---
 
## Part 1 — Docstring rules
 
### Format
 
All docstrings follow [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) and are compatible with `mkdocstrings[python]`.
 
**One-line docstring** — for simple functions and properties with no parameters worth documenting:
```python
def is_optional(self) -> bool:
    """Returns True if this field is not required by the spec."""
```
 
**Multi-line docstring** — for everything else:
```python
def read(path: Path, fmt: str | None = None, message_type: str | None = None) -> CCSDSDataMessage:
    """Reads a CCSDS ODM file and returns a validated domain model.
 
    Auto-detects format and message type from the file extension and content
    unless overrides are supplied. Detection follows CCSDS 502.0-B-3 §7.3.2
    (KVN) and §7.4.3 (XML).
 
    Args:
        path: Path to the input file. Accepts `str` or `pathlib.Path`.
        fmt: Format override. One of `"kvn"` or `"xml"`. If omitted, detected
            automatically.
        message_type: Message type override. One of `"oem"`, `"omm"`, `"opm"`,
            `"ocm"`. If omitted, detected automatically.
 
    Returns:
        A fully validated domain model instance. The concrete type corresponds
        to the message type (`OEM`, `OMM`, `OPM`, or `OCM`).
 
    Raises:
        ValueError: If the format or message type cannot be determined and no
            override is supplied.
        pydantic.ValidationError: If the file content violates the ODM spec
            constraints defined on the domain model.
        ParseError: If the file is structurally malformed (invalid KVN syntax,
            malformed XML, etc.).
 
    Example:
        ```python
        from ccsds.io import Reader
 
        msg = Reader.read("my_file.oem")
        msg = Reader.read("data.txt", fmt="kvn", message_type="oem")
        ```
    """
```
 
### Section order
 
Use exactly these sections, in this order, omitting any that do not apply:
 
1. Summary line (one sentence, imperative mood, no full stop for one-liners; full stop for multi-line summaries).
2. Blank line.
3. Extended description — explain *why* and *when*, not *how*. Include spec section references (`§5.2.4.1`) where the behaviour is driven by the standard.
4. `Args:` — every parameter, including `self`-less ones. Type goes in the annotation, not the docstring. Default values and valid options go here if not obvious.
5. `Returns:` — what is returned and its type. Omit if the return type is `None`.
6. `Yields:` — for generators.
7. `Raises:` — every exception the caller might need to handle. Do not document internal-only exceptions.
8. `Note:` — for non-obvious constraints, thread-safety warnings, or deprecation notices.
9. `Example:` — a minimal runnable snippet. Required on all public API methods. Optional on internal ones.
 
### Tone and content rules
 
- **Imperative mood** for summary lines: "Reads a file", "Returns the position vector", "Constructs an EphemerisData from a NumPy array." Not "This method reads…" or "Used to read…".
- **Spec citations belong in the docstring** when the behaviour is directly mandated by CCSDS 502.0-B-3. Format: `CCSDS 502.0-B-3 §5.2.4.1`. Inline code comments cite the section too, but the docstring is the user-visible record.
- **Units must be stated** on every field, parameter, and return value that carries physical units. Format: `x (float): X position in km.` Use the unit from `FieldMetadata` — do not invent units.
- **Do not restate the type annotation** in the description. The type is in the signature; the docstring adds meaning.
- **Do not describe the implementation.** Describe what the caller needs to know.
- **Optional fields** — state explicitly that the field is optional and what `None` means.
- **Pydantic models** — the class docstring describes what the model *represents*, not how Pydantic works. Do not mention `BaseModel`, `model_config`, or validators by name.
 
### Scope
 
| Location | Docstring required |
|---|---|
| Every module (`__init__.py` and named modules) | Yes — one-liner stating what the module contains |
| Every public class | Yes — multi-line |
| Every public method and function | Yes |
| Every public property | Yes — one-liner is fine |
| Every private method (`_name`) | Only if the logic is non-obvious; otherwise omit |
| Every dunder method (`__init__`, `__iter__`, etc.) | Only `__init__` if it has meaningful parameters beyond `self`; omit others |
| `conftest.py`, test files, example scripts | No |
 
### Domain model fields
 
Pydantic fields use `Field(description=...)` for their docstring equivalent. Every field must have a `description` that states:
- What the field represents.
- Its unit (if physical).
- Whether it is optional and what `None` means.
- The relevant spec keyword (`OBJECT_NAME`, `REF_FRAME`, etc.) and section reference if not already obvious from context.
 
Example:
```python
x: float = Field(..., description="X component of position in km. CCSDS keyword X. §5.2.4.1.")
message_id: str | None = Field(None, description="Optional message identifier. CCSDS keyword MESSAGE_ID. §5.2.2.")
```
 
### Specific docstring requirements by module
 
**`models/`** — domain model classes:
- Class docstring: what ODM message or sub-structure this represents, which spec section defines it, and a one-line summary of mandatory vs optional fields.
- Each nested class (`Metadata`, `EphemerisData`, `CovarianceMatrix`, etc.) gets its own class docstring.
- Cross-field invariants enforced by validators must be documented on the class, not the validator method.
**`io/reader.py`, `io/writer.py`** — facades:
- Class docstring: one sentence. These classes have no state; say so.
- Every method: full multi-line docstring with `Args`, `Returns`, `Raises`, and `Example`.
**`io/ports.py`** — protocols:
- Each Protocol class docstring must state: "Structural protocol — any class with a matching signature satisfies this interface without explicit inheritance."
**`io/detection.py`**:
- Function docstrings must state the detection priority order and cite spec sections for content-sniff rules.
**`io/registry.py`**:
- Module docstring must state that adapter classes are lazily imported.
- `get_reader` / `get_writer` docstrings must state what happens on a miss.
**`io/kvn/parser.py`**, **`io/xml/parser.py`**:
- Every parsing function must cite the spec section it implements in both the docstring and an inline comment.
- Return types must describe the structure of the plain-Python dict returned.
**`compute/backends/base.py`** — protocols:
- Each method docstring must state which direction of conversion it owns (domain → external or external → domain).
**`compute/backends/pure.py`**, **`numpy_.py`**, **`ostk_.py`**:
- Class docstring: which protocol(s) it satisfies and which optional dependency it requires (or "no optional dependencies" for pure).
- Methods that raise `NotImplementedError`: docstring must name the required extra and the install command.
- Unit conversion methods in `ostk_.py`: docstring must state the conversion factor and direction explicitly.
**`compute/views.py`**:
- Class docstrings must state: "This view holds a reference to the domain model — it does not copy data."
- `__call__` docstring must describe interpolation behaviour and delegate to the backend.
- `to_numpy()` / `to_ostk()` shortcut docstrings must state that they are convenience wrappers and name the backend they use.
**`compute/factories.py`**:
- Each factory function: full multi-line docstring. State that the result is a plain domain model (not a view), that it passes `check_epochs_ordered`, and that `backend` defaults to `PurePythonBackend()`.
**`compute/registry.py`**:
- `using_backend` docstring must include a `Note:` section stating: "Thread-local; not safe for use with asyncio or other concurrency primitives."
---
 
## Part 2 — MkDocs site
 
### Dependencies
 
```toml
[tool.poetry.dev-dependencies]
mkdocs = ">=1.5"
mkdocstrings = {extras = ["python"], version = ">=0.24"}
```
 
No `mkdocs-material` — use the default MkDocs theme.
 
### Site structure
 
```
docs/
├── index.md                  # Project overview and quick-start
├── user-guide/
│   ├── installation.md
│   ├── reading-and-writing.md
│   ├── compute.md
│   └── formats.md
├── api/
│   ├── reader-writer.md      # Reader, Writer
│   ├── models.md             # OEM, OMM, OPM, OCM and nested classes
│   ├── views.md              # EphemerisView, StateView, CovarianceView
│   ├── backends.md           # PurePythonBackend, NumpyBackend, OSTkBackend
│   └── factories.md         # ephemeris_from_propagator etc.
└── internals/
    ├── io-adapters.md        # KVN and XML adapters
    ├── detection.md          # detect_format, detect_message_type
    ├── registry.md           # get_reader, get_writer, using_backend
    └── parsers.md            # kvn/parser.py, xml/parser.py
```
 
### `mkdocs.yml`
 
```yaml
site_name: CCSDS ODM
site_description: Python implementation of the CCSDS 502.0-B-3 Orbit Data Message standard.
docs_dir: docs
theme:
  name: mkdocs
 
plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_category_heading: true
            members_order: source
            inherited_members: false
            filters:
              - "!^_"          # hide private by default; internals pages override this
 
nav:
  - Home: index.md
  - User Guide:
    - Installation: user-guide/installation.md
    - Reading and Writing: user-guide/reading-and-writing.md
    - Computation: user-guide/compute.md
    - Formats: user-guide/formats.md
  - API Reference:
    - Reader & Writer: api/reader-writer.md
    - Domain Models: api/models.md
    - Views: api/views.md
    - Backends: api/backends.md
    - Factories: api/factories.md
  - Internals:
    - I/O Adapters: internals/io-adapters.md
    - Detection: internals/detection.md
    - Registry: internals/registry.md
    - Parsers: internals/parsers.md
```
 
### API reference pages
 
Each page in `docs/api/` and `docs/internals/` uses `mkdocstrings` autodoc directives. Use the `::: ` syntax. Example for `docs/api/reader-writer.md`:
 
```markdown
# Reader & Writer
 
The primary interface for reading and writing CCSDS ODM files.
Auto-detection, format handling, and adapter selection are handled
internally — callers work only with paths and domain models.
 
## Reader
 
::: ccsds.io.reader.Reader
 
## Writer
 
::: ccsds.io.writer.Writer
```
 
Internals pages override the default `filters` to show private members:
 
```markdown
::: ccsds.io.kvn.parser
    options:
      filters: []
```
 
### `docs/index.md` content requirements
 
- One-paragraph description of what the library is and what standard it implements.
- A minimal quick-start code block showing `Reader.read()` and `Writer.write()`.
- A note that the library is a faithful implementation of CCSDS 502.0-B-3 — no extensions, no relaxations.
- Links to the User Guide and API Reference.
### `docs/user-guide/` content requirements
 
Each page is hand-written prose (not autodoc). Requirements:
 
**`installation.md`**: pip install command, optional extras (`[numpy]`, `[ostk]`), Python version requirement.
 
**`reading-and-writing.md`**: covers `Reader.read()` with and without overrides, `Writer.write()` with format inference and explicit override, and a round-trip example. All code blocks must be runnable.
 
**`compute.md`**: covers `EphemerisView`, `StateView`, `CovarianceView`, explicit `backend=` usage, `using_backend()` context manager (with thread-safety note), and factory functions. One section per concept. Code blocks use real class and method names.
 
**`formats.md`**: one section each for KVN and XML. Describes the block structure, cites the relevant spec sections, and shows a minimal annotated example of each format. No parsing logic — format description only.
 
---
 
## Change discipline
 
- Modify source files only to add or improve docstrings and `Field(description=...)` values.
- Do not change any logic, signatures, validators, field types, or default values.
- Do not add, remove, or reorder imports.
- Do not reformat code outside of docstring blocks.
- Do not add `__all__` declarations unless they are already present.
---
 
## Output format
 
1. List every source file modified, with a one-line summary of what was added or changed.
2. List every `docs/` file created.
3. Note any public API surface that was missing a docstring and could not be inferred from context — flag these for human review rather than guessing.
4. Then produce all files.
**Before writing anything, inspect the repository structure and list the public API surface you found. Confirm the module paths match the `mkdocs.yml` `:::` directives before generating the docs pages.**
