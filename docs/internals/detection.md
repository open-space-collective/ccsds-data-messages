# Detection

Format and message-type detection logic. Detection is pure - no side effects beyond
reading the minimum necessary bytes from the file, and no imports from `models/`,
`compute/`, or any adapter module.

::: orbit_data_messages.io.detection
    options:
      filters: []
