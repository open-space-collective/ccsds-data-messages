# SPDX-License-Identifier: Apache-2.0

"""
Public exception hierarchy for ``ccsds-data-messages``.
"""


class CCSDSError(Exception):
    """Base class for all ``ccsds-data-messages`` errors."""


class DetectionError(CCSDSError):
    """Format or message type cannot be determined from the given source."""


class UnsupportedAdapterError(CCSDSError):
    """No reader or writer is registered for the requested (format, message_type) pair."""


class ParseError(CCSDSError):
    """Message content is malformed and cannot be parsed into a domain model."""


class SpecViolationError(CCSDSError):
    """Parsed content violates a CCSDS 502.0-B-3 spec constraint."""
