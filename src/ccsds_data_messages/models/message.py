# SPDX-License-Identifier: Apache-2.0

"""
Abstract base class for all CCSDS data messages.
"""

from __future__ import annotations

from abc import ABC
from typing import Any
from typing import Self

from pydantic import ConfigDict

# Shared Pydantic configuration for all CCSDS data message classes.
#
# frozen=True           - messages are immutable records; mutation is a bug.
# strict=False          - allows str to StrEnum coercion ("EME2000" to RefFrame.EME2000).
# use_enum_values=False - store enum members, not raw strings, for type-safe access.
# populate_by_name=True - no field aliases used; harmless to enable.
# extra="forbid"        - unknown field names raise ValidationError at construction time,
#                         catching keyword typos that would otherwise produce silent wrong values.
CCSDS_MODEL_CONFIG: ConfigDict = ConfigDict(
    frozen=True,
    strict=False,
    use_enum_values=False,
    populate_by_name=True,
    extra="forbid",
)


class CCSDSDataMessage(ABC):
    """
    Abstract base for CCSDS data messages (OEM, OMM, OPM, OCM, etc.).

    Cannot be instantiated directly; use one of the concrete subtypes.

    Raises:
        TypeError: If instantiated directly (i.e. ``CCSDSDataMessage()``).
    """

    def __new__(
        cls: type[Self],
        *args: Any,
        **kwargs: Any
    ) -> Self:  # noqa: ARG004
        """
        Create a new instance, blocking direct instantiation of the abstract base.

        Args:
            cls (type[Self]): The class being instantiated.
            *args (Any): Positional arguments forwarded to ``super().__new__``.
            **kwargs (Any): Keyword arguments forwarded to ``super().__new__``.

        Returns:
            Self: A new instance of the concrete subclass.

        Raises:
            TypeError: If ``cls`` is ``CCSDSDataMessage`` itself.
        """
        if cls is CCSDSDataMessage:
            raise TypeError(
                "CCSDSDataMessage cannot be instantiated directly. "
                "Use a concrete message type: OEM, OMM, OPM, OCM, etc."
            )
        return super().__new__(cls)
