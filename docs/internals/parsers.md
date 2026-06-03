# Parsers

Low-level tokenizers for KVN and XML. Parsers produce plain Python types (`str`, `float`,
`int`, `list`, `dict`) only - no domain model types. Message-specific adapters consume
parser output and map it to domain model fields via `FieldMetadata` annotations.

## KVN parser

::: orbit_data_messages.io.kvn.parser
    options:
      filters: []

## XML parser

::: orbit_data_messages.io.xml.parser
    options:
      filters: []
