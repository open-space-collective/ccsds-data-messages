# Contributing

## Development setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/open-space-collective/ccsds-data-messages
cd ccsds-data-messages
uv sync --all-extras
```

Or use the Docker workflow (no local Python required):

```bash
make dev         # builds image and drops you into a shell
```

## Running checks

```bash
make check       # lint + format-check + typecheck + pylint + tests (full CI gate)
make test        # tests only
make lint        # ruff check
make typecheck   # mypy --strict
```

All checks must pass before a PR is merged. CI runs the same `make check` sequence.

## Pull request workflow

1. Fork the repo and create a branch from `main`.
2. Make your change. If it touches the spec compliance layer, add or update a fixture
   in `tests/fixtures/` and a parametrized case in `tests/integration/test_spec_conformance.py`.
   Some tests in that file are marked `# GAP` — they document a spec requirement the
   code doesn't yet meet and are *expected* to fail. Do not add `xfail` to a gap test;
   the failure is the signal that the gap still exists.
3. Run `make check` locally — fix any failures before opening the PR.
4. Open a PR against `main`. Fill in the PR template.
5. A maintainer will review. Expect feedback on spec citations if the change touches
   CCSDS-specific behaviour.

## Coding standards

- **Formatting**: `ruff format` (double quotes, 90-char line length). Run `make format`
  to apply.
- **Linting**: `ruff check` with `select = ["ALL"]`. See `pyproject.toml` for the
  project-specific ignore list and the rationale comments.
- **Types**: `mypy --strict` must pass. Pydantic model fields must be fully annotated.
  Use `Annotated[..., FieldMetadata(...)]` for all CCSDS keyword fields.
- **Tests**: `pytest`. New behaviour needs a test. Spec-compliance changes need a
  fixture test against the relevant Annex G example.

## Spec references

The CCSDS 502.0-B-3 specification PDF is in `specs/`. When adding or changing
behaviour, cite the relevant section in the docstring (e.g. `Section 5.2.4.1`).

## Known gaps

`docs/gaps.md` tracks spec compliance gaps and implementation limitations. If your
change addresses a tracked gap, remove or update the relevant entry.

## Reporting bugs

Open a GitHub issue using the **Bug report** template. Include the message type,
format (KVN or XML), and a minimal reproducing file or snippet.
