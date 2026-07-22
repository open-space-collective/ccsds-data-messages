# SPDX-License-Identifier: Apache-2.0

"""
NORAD Two-Line Element set (TLE) value object.

A TLE is *not* a CCSDS data message, so ``TLE`` deliberately does not subclass
``CCSDSDataMessage``; it is a small immutable value object. Produce one via
``ccsds_data_messages.omm_to_tle`` (``models/conversions.py``); the fixed-column
encoding, checksum, and Alpha-5 satellite numbers live in ``models/_tle_codec.py``.
This module holds only the data type and its rendering.

Both element lines are 69 characters, 1-indexed, with the checksum in column 69
(https://www.space-track.org/documentation#tle).
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import model_validator

_TLE_LINE_LENGTH = 69


class TLE(BaseModel):
    """
    A NORAD Two-Line Element set.

    Immutable value object holding the satellite name and the two element lines
    (each 69 characters, checksum included). Obtain one via
    ``ccsds_data_messages.omm_to_tle``.

    ``str(tle)`` yields the bare two-line form; ``three_line()`` prepends the
    space-track ``"0 NAME"`` title line.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    line1: str
    line2: str

    @model_validator(mode="after")
    def _validate_lines(self) -> TLE:
        for number, line in ((1, self.line1), (2, self.line2)):
            if len(line) != _TLE_LINE_LENGTH:
                raise ValueError(
                    f"TLE line {number} must be {_TLE_LINE_LENGTH} characters, "
                    f"got {len(line)}: {line!r}"
                )
            if not line.startswith(str(number)):
                raise ValueError(f"TLE line {number} must begin with '{number}'.")
        return self

    def two_line(self) -> str:
        """Return the two-line form (line 1 and line 2, newline-separated)."""
        return f"{self.line1}\n{self.line2}"

    def three_line(self) -> str:
        """Return the space-track three-line form: ``"NAME"`` then the two lines."""
        return f"{self.name}\n{self.line1}\n{self.line2}"

    def __str__(self) -> str:
        return self.two_line()
