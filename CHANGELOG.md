# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- OPM, OMM, OEM, and OCM domain models (CCSDS 502.0-B-3) as immutable, validated
  Pydantic models, with fluent builders for constructing them programmatically.
- KVN and XML readers and writers for all four message types, with format and
  message-type auto-detection.
- `WriterOptions` for controlling keyword alignment, unit annotations, float
  formatting, and suppression of spec-default values.
- Shared CCSDS epoch parsing/formatting, `FieldMetadata`/`Delineation` I/O
  introspection annotations, and Annex B controlled-vocabulary `StrEnum` types.
- Reader/writer registry and port protocols for extending the library with
  additional formats or message types.
- `oem_to_tracss_ocm` conversion from OEM to a TraCSS-compliant OCM.
