# SPDX-License-Identifier: Apache-2.0

"""
Annotated type aliases for CCSDS data message blocks.

Each alias bundles the Python type, a Pydantic Field (description + default where
uniform), a structural validator, and a FieldMetadata keyword. This allows model fields
to reference a single alias rather than repeating a four-layer Annotated declaration.

Why CCSDS date/time fields are modeled as ``str`` rather than ``datetime``:

    Section 7.5.10 defines two interchangeable wire formats, called calendar
    (``YYYY-MM-DDThh:mm:ss[.d+]``) and day-of-year (``YYYY-DOYThh:mm:ss[.d+]``)
    and permits either in any field. Converting to ``datetime`` at construction time
    would (a) silently canonicalize the format, losing the wire representation that
    the sender chose, and (b) erase the time-system semantics: GPS, TAI, and UTC
    epochs all parse to ``datetime(... tzinfo=UTC)`` but carry different physical
    meanings that cannot be encoded without the ``astropy`` dependency.

    Preserving the wire ``str`` keeps the model faithfully "round-trippable" and
    leaves format decisions to I/O adapters. Callers that need datetime arithmetic
    must use ``parse_ccsds_epoch(field_value, time_system)`` which returns a
    ``TimeScaledEpoch`` class, which is a Pydantic dataclass pairing the ``datetime``
    with its ``TimeSystem`` and raising on cross-scale comparisons.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic.functional_validators import AfterValidator

from ._epoch import validate_ccsds_date, validate_time_tag
from ._fields import FieldMetadata
from ._validators import (
    _validate_comment,
    _validate_negative_mass,
    _validate_oem_version,
    _validate_omm_version,
    _validate_opm_version,
    _validate_optional_ccsds_date,
    _validate_optional_time_tag,
    _validate_version_format,
)

Comment = Annotated[
    list[str] | None,
    Field(
        default=None,
        description=(
            "Comment format rules are defined in section 7.8. "
            "A comment must be a non-empty list of strings, or None."
        ),
    ),
    AfterValidator(_validate_comment),
    FieldMetadata(keyword="COMMENT"),
]

CreationDate = Annotated[
    str,
    Field(
        description=(
            "File creation date/time in UTC. "
            "Accepts calendar (YYYY-MM-DDThh:mm:ss[Z]) and "
            "day-of-year (YYYY-DOYThh:mm:ss[Z]) formats per CCSDS section 7.5.10."
        )
    ),
    AfterValidator(validate_ccsds_date),
    FieldMetadata(keyword="CREATION_DATE"),
]

# Partial aliases: type + validator only; keyword and description stay inline.
# Example: field: Annotated[CcsdsDate, Field(...), FieldMetadata(keyword="FOO")]

VersionStr = Annotated[str, AfterValidator(_validate_version_format)]  # OCM only: 3.x
OPMVersionStr = Annotated[str, AfterValidator(_validate_opm_version)]  # {1.0, 2.0, 3.0}
OMMVersionStr = Annotated[str, AfterValidator(_validate_omm_version)]  # {2.0, 3.0}
OEMVersionStr = Annotated[str, AfterValidator(_validate_oem_version)]  # {1.0, 2.0, 3.0}

CCSDSDate = Annotated[str, AfterValidator(validate_ccsds_date)]

OptionalCCSDSDate = Annotated[str | None, AfterValidator(_validate_optional_ccsds_date)]

TimeTag = Annotated[str, AfterValidator(validate_time_tag)]

CCSDSTimeTag = Annotated[str | None, AfterValidator(_validate_optional_time_tag)]

NegativeMass = Annotated[float | None, AfterValidator(_validate_negative_mass)]
