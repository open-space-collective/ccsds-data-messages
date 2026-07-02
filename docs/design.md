# Design decisions

This page explains what the library does, and what it deliberately leaves out.

## What the library does

`ccsds-data-messages` reads, writes, and validates CCSDS 502.0-B-3 Orbit Data Messages.
Its scope is the message itself: the on-disk or on-wire representation and its
conformance to the standard. Concretely, it provides:

- **The four ODM types** (OPM, OMM, OEM, OCM) as typed domain models.
- **Two serializations** for every type: KVN (plain-text `KEY = VALUE`) and XML.
- **Validate-on-construction models.** Each message is a Pydantic model that validates
  when it is built. An instance is either fully spec-conformant or it does not exist, so
  a value read back from a file has already passed the same checks as one built by hand.
- **Format and message-type auto-detection**, so `read` can accept a file without being
  told what it is.
- **An open adapter registry.** `register_reader` and `register_writer` let an
  application plug in its own format adapters and dispatch to them through the same
  `read` / `write` entry points.
- **Output formatting control** through `WriterOptions` (keyword alignment, unit
  attributes, float formatting, suppressing default-valued fields).

## What it deliberately leaves out

The library is a read/write/validate layer, not an astrodynamics engine. The following
are out of scope by design.

### Orbit mechanics

No propagation, no coordinate-frame transforms, and no interpolation math. The library
carries the numbers the message declares and checks their form; it does not compute new
states from them. Turning an OEM's tabulated states into a state at an arbitrary epoch,
or rotating a covariance between frames, is the caller's job.

### Consumer processing rules

The spec contains rules addressed to the consumer of a message rather than to its
content. Examples are OEM cross-segment interpolation (section 5.2.4.6) and OCM
composite-maneuver summation (section 6.2.8.11). These describe how a downstream tool
should use the data, not what a conformant message may contain, so the library does not
perform them. Where it helps, it exposes guardrails instead of doing the computation,
such as `OEM.get_segment_for_epoch()`, which hands back the single segment that covers
an epoch so a caller interpolates within it rather than across a boundary.

### Registry-membership validation

Several fields draw their values from the SANA registry, which the spec frames as a
live, extensible resource. Whether a given `ORIGINATOR` or reference-frame name is a
currently registered member is an application-layer concern that changes over time, so
these fields accept free text. Where the spec says a value "should" come from a fixed
set but permits ICD-agreed alternatives, the field accepts either the typed enum or a
plain string (for example `RefFrame | str`), so a parametric or non-standard name is not
rejected outright. A "shall" from a fixed set is enforced.

### Registry-driven column typing for raw data lines

Some OCM blocks (trajectory and covariance time histories) have a column schema chosen
at runtime by a registry-backed keyword such as `TRAJ_TYPE` or `COV_TYPE`, not by a
fixed table. Because the columns cannot be typed at class-definition time, those lines
are kept as raw strings and their per-element content is not validated. Maneuver lines
are the tractable case, since their columns come from the fixed tables via
`MAN_COMPOSITION`, and those are fully typed and validated.

## Why validate-on-construction

Making a model impossible to build in an invalid state removes a whole class of bugs
from the caller's side: there is no "is this parsed object actually valid yet" step, no
half-populated object to guard against, and reading a file exercises exactly the same
validation as constructing a message in code. The cost is that the models are strict,
including rejecting unknown keywords rather than silently dropping them, which is the
intended behavior for a conformance-checking library.
