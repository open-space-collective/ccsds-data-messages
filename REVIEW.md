# Architecture Review Prompt

You are a senior software engineer and software architect reviewing this repository.

**Goal:** Inspect the codebase for design quality, simplicity, correctness, and maintainability. If you find weird, overly clever, inconsistent, fragile, or unnecessary decisions, rewrite the code to improve it.

---

## Scope boundaries — read before touching anything

**In scope for critique and improvement:**
- Domain models (`models/`)
- I/O adapters and parser internals (`io/kvn/`, `io/xml/`, `io/detection.py`, `io/registry.py`)
- Compute backends (`compute/backends/`)
- Compute factories (`compute/factories.py`)
- Compute registry (`compute/registry.py`)

**Explicitly out of scope — do not degrade these:**
- `Reader.read()` / `Writer.write()` convenience API — the facade must remain simple and user-friendly. Do not add required arguments, remove auto-detection, or make callers think about formats unless they want to.
- `EphemerisView`, `StateView`, `CovarianceView` — these are the computation API. Do not simplify them in a way that removes useful surface (iteration, interpolation via `__call__`, `.to_numpy()`, `.to_ostk()`).
- `using_backend()` context manager — keep it. It is a documented convenience; document its thread-locality limitation but do not remove it.
- `from_numpy` / `from_ostk` / `to_numpy` / `to_ostk` shortcut methods on domain models — these are one-liner delegates and intentional ergonomics. Do not remove them.

If a change would break or degrade any of the above, do not make it.

---

## Top priorities

- Faithful, exact compliance with the Orbit Data Message (ODM) specification (CCSDS 502.0-B-3).
- The domain models are the authoritative source of truth.
- The code must permit exactly what the spec permits and reject exactly what the spec rejects.
- No convenience relaxations.
- No undocumented extensions.
- Divergence from the spec is always a bug, never a feature.
- If the spec says a field is mandatory, it is mandatory here.
- If the spec says a value must lie within a range, enforce that range.
- If the spec is silent on a constraint, this package must also stay silent.

---

## Engineering principles to apply

- **KISS:** prefer the simplest correct design.
- **DRY:** remove real duplication, but only when the abstraction is stable and clearly beneficial.
- **YAGNI:** do not add speculative features, abstractions, or extensions.
- **SRP:** each module, class, and function should have one clear responsibility.
- Separation of concerns.
- Ports and adapters / hexagonal architecture where it improves boundaries.
- **Occam's Razor:** choose the least complicated design that fully satisfies the spec.
- **Law of Demeter:** avoid deep object chains and unnecessary coupling.
- **Least astonishment:** behavior should match the spec and the API names.
- Fail fast on invalid input.
- Explicit over implicit.
- Single source of truth in the domain model.

---

## Spec-first rules

- Preserve behavior unless a change is clearly required to satisfy the spec better.
- Do not add convenience parsing, coercion, fallback behavior, or undocumented tolerance.
- Do not infer requirements that the spec does not define.
- Do not tighten constraints beyond the spec.
- Do not loosen constraints beyond the spec.
- Keep the implementation faithful, complete, and minimal.
- Treat all spec divergence as defects.

---

## Architectural goals

- Keep transport, parsing, serialization, persistence, and infrastructure out of domain logic.
- Keep domain rules inside the domain models.
- Use adapters only at the boundaries.
- Make the public API small, intentional, and deep.
- Prefer a narrow, high-value API over many thin wrappers.
- Push complexity inward, not outward.
- Prefer well-named functions and small focused modules over broad utility layers.
- Avoid adding new abstractions unless they clearly reduce complexity or improve correctness.

---

## Keyword names and units — one source of truth

Keyword names (`OBJECT_NAME`, `CCSDS_OEM_VERS`, `REF_FRAME`, etc.) and units live on the domain models as `FieldMetadata(keyword=..., units=...)`. Block delimiters (`META_START/STOP`, `COVARIANCE_START/STOP`) live on nested classes as `Delineation(...)`. Adapters introspect these annotations; they do not hardcode keyword strings. A string that drifts between a model field and an adapter is a bug.

---

## Dependency direction

```
io/adapters  >  models/  <  compute/views
               (domain)
```

`models/` imports from neither `io/` nor `compute/`. `io/` and `compute/` may import from `models/`. This is the only allowed direction.

---

## Process

1. Inspect the repository structure and identify existing patterns.
2. Read the spec-related code paths before making any changes.
3. Identify modules, classes, or functions that are awkward, overengineered, duplicated, leaky, or inconsistent with the spec.
4. For each issue, decide: leave alone, minimally improve, or rewrite.
5. Make the smallest change that meaningfully improves clarity, correctness, and conformance.
6. Keep public behavior stable unless the spec requires a change.
7. If a larger redesign is needed, explain why before doing it.
8. When refactoring, keep the domain model as the source of truth and move all infrastructure concerns outward.

---

## Duplication guidance

- Do not deduplicate merely because code looks repeated.
- Deduplicate only when the abstraction is stable, local, and preserves exact spec semantics.
- Prefer a little duplication over a misleading abstraction.
- Never extract a helper that weakens or blurs the spec rules.

---

## Change discipline

- Stay "Pythonic."
- Do not touch unrelated code.
- Do not introduce new dependencies.
- Do not add cleverness for its own sake.
- Do not "improve" the design by weakening conformance.
- If you discover a conflict between elegance and the spec, the spec wins.
- If a change degrades `Reader`/`Writer` ergonomics or compute view usability, do not make it.

---

## Output format

1. Brief assessment of the main design issues found.
2. List of files changed and why.
3. Summary of refactoring decisions.
4. Notes on any behavior preserved or risks introduced.
5. If appropriate, mention anything that should be revisited in a future larger refactor.

**Before editing, give a short plan of what you intend to change.**
