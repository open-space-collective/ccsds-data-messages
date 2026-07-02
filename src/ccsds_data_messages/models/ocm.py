# Copyright (c) Loft Orbital Solutions Inc.
from __future__ import annotations

import re
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Annotated
from typing import Any
from typing import ClassVar
from typing import Literal
from typing import TypeVar
from typing import cast

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from ._aliases import CCSDSDate
from ._aliases import CCSDSTimeTag
from ._aliases import Comment
from ._aliases import OptionalCCSDSDate
from ._aliases import TimeTag
from ._aliases import VersionStr
from ._base import BaseHeader
from ._epoch import _CCSDS_DATE_RE
from ._epoch import _REL_TIME_TAG_RE
from ._epoch import _normalize_epoch
from ._epoch import _parse_ccsds_epoch
from ._fields import Delineation
from ._fields import FieldMetadata
from .message import CCSDS_MODEL_CONFIG
from .message import CCSDSDataMessage
from .values import CenterName
from .values import CovarianceOrdering
from .values import CovarianceType
from .values import DutyCycleType
from .values import ExtendedManCovRefFrame
from .values import Interpolation
from .values import ManeuverBasis
from .values import ManeuverPurpose
from .values import ObjectType
from .values import OperationalStatus
from .values import OrbitalElements
from .values import OrbitCategory
from .values import RefFrame
from .values import ShadowModel
from .values import TimeSystem

_TagKey = TypeVar("_TagKey", float, str)


def _assert_strictly_increasing(
    keys: list[_TagKey], tags: list[str], block_name: str
) -> None:
    """Raise if `keys` (aligned 1:1 with `tags`, for error messages) is not strictly increasing."""
    for i in range(1, len(keys)):
        if keys[i] <= keys[i - 1]:
            raise ValueError(
                f"Time tags in the {block_name} block must be strictly increasing. "
                f"Line {i} has tag '{tags[i]}', which is not greater than the "
                f"previous tag '{tags[i - 1]}'."
            )


def _assert_no_duplicates(keys: list[_TagKey], tags: list[str], block_name: str) -> None:
    """Raise if `keys` (aligned 1:1 with `tags`, for error messages) contains a duplicate."""
    seen: set[_TagKey] = set()
    for i, key in enumerate(keys):
        if key in seen:
            raise ValueError(
                f"Duplicate time tag '{tags[i]}' in {block_name} block (section 6.2.2.4)."
            )
        seen.add(key)


def _classify_time_tags(tags: list[str], block_name: str) -> list[float] | list[str]:
    """
    Classify a block's time tags as relative or absolute, and verify all match.

    The format (relative seconds vs. absolute CCSDS date) is detected from the
    first tag; every subsequent tag must match that same format, since section
    6.2.2.5 forbids mixing absolute and relative tags within one data block.
    Without this check, a stray tag in the other format would silently pass
    through unvalidated (relative tags aren't range-checked; absolute tags
    aren't format-checked by ``_normalize_epoch``, which only reformats
    day-of-year dates and otherwise returns its input unchanged).

    Returns:
        list[float] | list[str]: Relative tags as floats, or absolute tags as
        ``_normalize_epoch``-normalized strings, both sortable for comparison.

    Raises:
        ValueError: If any tag does not match the format established by the
            first tag.
    """
    is_relative: bool = _REL_TIME_TAG_RE.fullmatch(tags[0]) is not None
    for i, tag in enumerate(tags):
        matches = (
            _REL_TIME_TAG_RE.fullmatch(tag)
            if is_relative
            else _CCSDS_DATE_RE.fullmatch(tag)
        )
        if not matches:
            expected = "relative" if is_relative else "absolute"
            raise ValueError(
                f"Time tags in the {block_name} block must not mix absolute and "
                f"relative formats (section 6.2.2.5). Line {i} has tag {tag!r}, which "
                f"does not match the {expected} format established by the first "
                f"tag {tags[0]!r}."
            )
    if is_relative:
        return [float(t) for t in tags]
    return [_normalize_epoch(t) for t in tags]


def _compare_same_format_time_tags(a: str, b: str) -> int | None:
    """
    Three-way compare two CCSDS time tags, or ``None`` if formats differ.

    Returns -1/0/1 for ``a`` <, ==, > ``b`` when both are relative (numeric
    seconds) or both absolute (CCSDS dates). Returns ``None`` when one is relative
    and the other absolute: reconciling those needs EPOCH_TZERO (which lives on
    OCM.Metadata, not on an individual block), so such pairs cannot be ordered here.
    """
    a_rel: bool = _REL_TIME_TAG_RE.fullmatch(a) is not None
    b_rel: bool = _REL_TIME_TAG_RE.fullmatch(b) is not None
    if a_rel and b_rel:
        fa, fb = float(a), float(b)
        return (fa > fb) - (fa < fb)
    a_abs: bool = _CCSDS_DATE_RE.fullmatch(a) is not None
    b_abs: bool = _CCSDS_DATE_RE.fullmatch(b) is not None
    if a_abs and b_abs:
        na, nb = _normalize_epoch(a), _normalize_epoch(b)
        return (na > nb) - (na < nb)
    return None


def _resolve_time_tag(tag: str, epoch_tzero: str) -> datetime:
    """
    Resolve an OCM maneuver time tag to an absolute ``datetime``.

    Relative tags (seconds) are offset from ``EPOCH_TZERO``; absolute tags are
    parsed directly. Used to order DC window/execution tags when they mix formats
    within one block - same-format pairs are ordered without EPOCH_TZERO inside
    ``ManeuverSpecification``; mixed pairs are reconciled at the OCM level, where
    ``EPOCH_TZERO`` is available.
    """
    if _REL_TIME_TAG_RE.fullmatch(tag):
        return _parse_ccsds_epoch(epoch_tzero) + timedelta(seconds=float(tag))
    return _parse_ccsds_epoch(tag)


def _check_data_lines_ordered(data_lines: list[str], block_name: str) -> None:
    """
    Assert that data_lines are strictly increasing by time tag.

    Detects relative vs absolute tags from the first line and compares
    accordingly (section 6.2.2.5 forbids mixing within a block). Strict ordering
    also enforces the no-duplicate rule of section 6.2.2.4.

    Use this for trajectory and covariance blocks (section 6.2.5.6 requires monotonic ordering).
    For maneuver blocks, use _check_no_duplicate_time_tags instead (section 6.2.8 has no
    ordering requirement - only section 6.2.2.4's no-duplicate rule applies).

    Args:
        data_lines (list[str]): Raw data lines to validate.
        block_name (str): Section name used in error messages (e.g.
            `"trajectory state"`).

    Returns:
        None

    Raises:
        ValueError: If any time tag is not strictly greater than the preceding one.
    """
    if len(data_lines) < 2:
        return
    tags: list[str] = [line.split()[0] for line in data_lines]
    keys: list[float] | list[str] = _classify_time_tags(tags, block_name)
    if isinstance(keys[0], float):
        _assert_strictly_increasing(cast("list[float]", keys), tags, block_name)
    else:
        _assert_strictly_increasing(cast("list[str]", keys), tags, block_name)


def _check_no_duplicate_time_tags(tags: list[str], block_name: str) -> None:
    """
    Reject duplicate time tags in a data block (section 6.2.2.4).

    Normalizes relative tags to float and absolute tags via _normalize_epoch before
    comparing, so '1.5' and '1.50' are treated as the same tag.

    Unlike _check_data_lines_ordered, this does not require monotonic ordering -
    section 6.2.8 imposes no ordering requirement on maneuver lines.

    Args:
        tags (list[str]): The time-tag token of each data line. Maneuver data is
            stored as typed rows, so callers pass ``[row.time_tag for row in ...]``.
        block_name (str): Section name used in error messages.

    Raises:
        ValueError: If any time tag appears more than once.
    """
    if len(tags) < 2:
        return
    keys: list[float] | list[str] = _classify_time_tags(tags, block_name)
    if isinstance(keys[0], float):
        _assert_no_duplicates(cast("list[float]", keys), tags, block_name)
    else:
        _assert_no_duplicates(cast("list[str]", keys), tags, block_name)


class OCM(CCSDSDataMessage, BaseModel):
    """
    Orbit Comprehensive Message (OCM).

    The OCM aggregates and extends OMM, OPM, and OEM content in a single hybrid
    message. It emphasizes flexibility and message conciseness by offering extensive
    optional standardized content while minimizing mandatory content.

    The OCM shall consist of orbit data for a single space object (or, in a
    parent/child deployment scenario, a single parent object).

    Structure (table 6-1):
    - Header                  (mandatory)
    - Metadata                (mandatory, exactly one)
    - Trajectory state blocks (optional, repeatable)
    - Physical properties     (optional, at most one)
    - Covariance blocks       (optional, repeatable)
    - Maneuver blocks         (optional, repeatable)
    - Perturbations           (conditional: required if OD section present)
    - Orbit determination     (optional, at most one)
    - User-defined parameters (optional, at most one)

    Note: field order within nested classes follows CCSDS 502.0-B-3 table order,
    not required-before-optional. This is intentional for spec traceability.
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "ocm"

    class Header(BaseHeader):
        """
        OCM header block (table 6-1).

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID.
        The five shared fields and their validators are inherited from BaseHeader.
        """

        ccsds_ocm_vers: Annotated[
            VersionStr,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OCM_VERS", order=0),
        ]

    class Metadata(BaseModel):
        """
        Single metadata section for the OCM (table 6-3).

        OBJECT_NAME, INTERNATIONAL_DESIGNATOR, and OBJECT_DESIGNATOR are each
        individually optional; it is recommended that at least one of the three
        object-identification keywords be supplied (note 2 to 6.2.4).

        TIME_SYSTEM and EPOCH_TZERO are mandatory (6.2.4 table 6-3).

        SCLK_OFFSET_AT_EPOCH and SCLK_SEC_PER_SI_SEC are conditional:
        they shall be supplied when TIME_SYSTEM = 'SCLK' (table 6-3).

        NEXT_LEAP_TAIMUTC is conditional:
        it should be provided when NEXT_LEAP_EPOCH is supplied (table 6-3).
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("META_START", "META_STOP")
        _xml_tag: ClassVar[str] = "metadata"

        comment: Comment = None

        # Object identification - all individually optional; at least one recommended.
        object_name: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Free-text field containing the name of the object. "
                    "Recommended to use UN OOSA designator index names. "
                    "Set to 'UNKNOWN' if unknown or cannot be disclosed."
                ),
            ),
            FieldMetadata(keyword="OBJECT_NAME"),
        ] = None

        international_designator: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "International COSPAR designator for the object. "
                    "Format: YYYY-NNNP{PP}. Set to 'UNKNOWN' if unavailable."
                ),
            ),
            FieldMetadata(keyword="INTERNATIONAL_DESIGNATOR"),
        ] = None

        catalog_name: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Satellite catalog source from which OBJECT_DESIGNATOR was obtained. "
                    "Value drawn from SANA Registry of Space Object Catalogs or Organizations."
                ),
            ),
            FieldMetadata(keyword="CATALOG_NAME"),
        ] = None

        object_designator: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique satellite identification designator as reflected in CATALOG_NAME. "
                    "Set to 'UNKNOWN' if not known or cannot be disclosed."
                ),
            ),
            FieldMetadata(keyword="OBJECT_DESIGNATOR"),
        ] = None

        alternate_names: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Free-text comma-delimited field containing alternate name(s,) of "
                    "this space object."
                ),
            ),
            FieldMetadata(keyword="ALTERNATE_NAMES"),
        ] = None

        # Originator contact info
        originator_poc: Annotated[
            str | None,
            Field(
                default=None,
                description="Originator or programmatic Point-of-Contact (PoC,) for OCM.",
            ),
            FieldMetadata(keyword="ORIGINATOR_POC"),
        ] = None

        originator_position: Annotated[
            str | None,
            Field(
                default=None,
                description="Contact position of the originator PoC.",
            ),
            FieldMetadata(keyword="ORIGINATOR_POSITION"),
        ] = None

        originator_phone: Annotated[
            str | None,
            Field(
                default=None,
                description="Originator PoC phone number.",
            ),
            FieldMetadata(keyword="ORIGINATOR_PHONE"),
        ] = None

        originator_email: Annotated[
            str | None,
            Field(
                default=None,
                description="Originator PoC email address.",
            ),
            FieldMetadata(keyword="ORIGINATOR_EMAIL"),
        ] = None

        originator_address: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Originator's physical address (suggest comma-delimited address lines,)."
                ),
            ),
            FieldMetadata(keyword="ORIGINATOR_ADDRESS"),
        ] = None

        # Technical contact info
        tech_org: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Creating agency or operator (value drawn from the SANA Organizations registry,)."
                ),
            ),
            FieldMetadata(keyword="TECH_ORG"),
        ] = None

        tech_poc: Annotated[
            str | None,
            Field(
                default=None,
                description="Technical PoC for OCM.",
            ),
            FieldMetadata(keyword="TECH_POC"),
        ] = None

        tech_position: Annotated[
            str | None,
            Field(
                default=None,
                description="Contact position of the technical PoC.",
            ),
            FieldMetadata(keyword="TECH_POSITION"),
        ] = None

        tech_phone: Annotated[
            str | None,
            Field(
                default=None,
                description="Technical PoC phone number.",
            ),
            FieldMetadata(keyword="TECH_PHONE"),
        ] = None

        tech_email: Annotated[
            str | None,
            Field(
                default=None,
                description="Technical PoC email address.",
            ),
            FieldMetadata(keyword="TECH_EMAIL"),
        ] = None

        tech_address: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Technical PoC physical address (suggest comma-delimited address lines,)."
                ),
            ),
            FieldMetadata(keyword="TECH_ADDRESS"),
        ] = None

        # Message linkage
        previous_message_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "ID that uniquely identifies the previous message from this originator "
                    "for this space object. May be provided without PREVIOUS_MESSAGE_EPOCH."
                ),
            ),
            FieldMetadata(keyword="PREVIOUS_MESSAGE_ID"),
        ] = None

        next_message_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "ID that uniquely identifies the next message from this originator "
                    "for this space object. May be provided without NEXT_MESSAGE_EPOCH."
                ),
            ),
            FieldMetadata(keyword="NEXT_MESSAGE_ID"),
        ] = None

        # Cross-message links
        adm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Attitude Data Message(s,) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="ADM_MSG_LINK"),
        ] = None

        cdm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Conjunction Data Message(s,) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="CDM_MSG_LINK"),
        ] = None

        prm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Pointing Request Message(s,) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="PRM_MSG_LINK"),
        ] = None

        rdm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Reentry Data Message(s,) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="RDM_MSG_LINK"),
        ] = None

        tdm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-separated list of file name(s,) and/or identification number(s) "
                    "of Tracking Data Message(s) upon which this OD is based."
                ),
            ),
            FieldMetadata(keyword="TDM_MSG_LINK"),
        ] = None

        # Space object metadata
        operator: Annotated[
            str | None,
            Field(
                default=None,
                description="Operator of the space object.",
            ),
            FieldMetadata(keyword="OPERATOR"),
        ] = None

        owner: Annotated[
            str | None,
            Field(
                default=None,
                description="Owner of the space object.",
            ),
            FieldMetadata(keyword="OWNER"),
        ] = None

        country: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name, code, or abbreviation of the country where the space object "
                    "owner is based."
                ),
            ),
            FieldMetadata(keyword="COUNTRY"),
        ] = None

        constellation: Annotated[
            str | None,
            Field(
                default=None,
                description="Name of the constellation to which this space object belongs.",
            ),
            FieldMetadata(keyword="CONSTELLATION"),
        ] = None

        object_type: Annotated[
            ObjectType | str | None,
            Field(
                default=None,
                description=(
                    "Type of object. Select from annex B, subsection B11 "
                    "(https://sanaregistry.org/r/object_types,). "
                    "Non-standard values are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="OBJECT_TYPE"),
        ] = None

        # Time system - mandatory with default UTC (table 6-3)
        time_system: Annotated[
            TimeSystem | str,
            Field(
                description=(
                    "Time system for all absolute time stamps in this OCM including "
                    "EPOCH_TZERO. Section 3.2.3.2/Annex B3 lists the standard set (advisory "
                    "'should' language); ICD-specific values are accepted as plain str. "
                    "Default is UTC. If SCLK is selected, SCLK_OFFSET_AT_EPOCH and "
                    "SCLK_SEC_PER_SI_SEC shall be supplied."
                ),
            ),
            FieldMetadata(keyword="TIME_SYSTEM"),
        ] = TimeSystem.UTC

        # Epoch - mandatory
        epoch_tzero: Annotated[
            CCSDSDate,
            Field(
                description=(
                    "Default epoch to which all relative times are referenced in data blocks. "
                    "For SCLK timescale, this is interpreted as UTC. "
                    "See 7.5.10 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="EPOCH_TZERO"),
        ]

        # Optional / operational metadata
        ops_status: Annotated[
            OperationalStatus | str | None,
            Field(
                default=None,
                description=(
                    "Operational status of the space object. Select from annex B, "
                    "subsection B12 (https://sanaregistry.org/r/operational_status,). "
                    "Non-standard values are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="OPS_STATUS"),
        ] = None

        orbit_category: Annotated[
            OrbitCategory | str | None,
            Field(
                default=None,
                description=(
                    "Type of orbit. Select from annex B, subsection B14 "
                    "(https://sanaregistry.org/r/orbit_categories,). "
                    "Examples: GEO, LEO, MEO, HEO, SUPER-GEO. "
                    "Non-standard values are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="ORBIT_CATEGORY"),
        ] = None

        ocm_data_elements: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-delimited list of data block type codes included in this message, "
                    "in message order. Values confined to: ORB, PHYS, COV, MAN, PERT, OD, USER. "
                    "Repeated entries (e.g., ORB, ORB,) indicate multiple blocks of that type."
                ),
            ),
            FieldMetadata(keyword="OCM_DATA_ELEMENTS"),
        ] = None

        @field_validator("ocm_data_elements")
        @classmethod
        def _validate_ocm_data_elements(cls, v: str | None) -> str | None:
            if v is None:
                return v
            _valid: frozenset[str] = frozenset(
                {"ORB", "PHYS", "COV", "MAN", "PERT", "OD", "USER"}
            )
            tokens = [t.strip().upper() for t in v.split(",")]
            if invalid := [t for t in tokens if t not in _valid]:
                raise ValueError(
                    f"OCM_DATA_ELEMENTS tokens must be from "
                    f"{{ORB, PHYS, COV, MAN, PERT, OD, USER}}, got: {invalid} (table 6-3)."
                )
            return v

        # SCLK fields - conditional on TIME_SYSTEM = SCLK
        sclk_offset_at_epoch: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Number of spacecraft clock counts existing at EPOCH_TZERO. [s] "
                    "Default 0.0. Shall be provided when TIME_SYSTEM = SCLK."
                ),
            ),
            FieldMetadata(
                keyword="SCLK_OFFSET_AT_EPOCH",
                units="s",
            ),
        ] = None

        sclk_sec_per_si_sec: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Current number of clock seconds per SI second. [s] "
                    "Default 1.0. Shall be provided when TIME_SYSTEM = SCLK."
                ),
            ),
            FieldMetadata(
                keyword="SCLK_SEC_PER_SI_SEC",
                units="s",
            ),
        ] = None

        # Message epoch linkage
        previous_message_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Creation epoch of the previous message from this originator for this "
                    "space object. May be provided without PREVIOUS_MESSAGE_ID. "
                    "See 7.5.10 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="PREVIOUS_MESSAGE_EPOCH"),
        ] = None

        next_message_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Anticipated (or actual,) epoch of the next message from this originator "
                    "for this space object. May be provided without NEXT_MESSAGE_ID. "
                    "See 7.5.10 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="NEXT_MESSAGE_EPOCH"),
        ] = None

        # Coverage times (relative or absolute)
        start_time: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Time of the earliest data contained in the OCM. "
                    "Specified as either a relative or absolute time tag."
                ),
            ),
            FieldMetadata(keyword="START_TIME"),
        ] = None

        stop_time: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Time of the latest data contained in the OCM. "
                    "Specified as either a relative or absolute time tag."
                ),
            ),
            FieldMetadata(keyword="STOP_TIME"),
        ] = None

        time_span: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Span of time that the OCM covers, measured in days. [d] "
                    "Defined as (STOP_TIME - START_TIME,) in days."
                ),
            ),
            FieldMetadata(
                keyword="TIME_SPAN",
                units="d",
            ),
        ] = None

        # Time correction / leap second data
        taimutc_at_tzero: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Difference (TAI - UTC,) in seconds (total leap seconds since 1958) "
                    "as modeled by the originator at EPOCH_TZERO. [s]"
                ),
            ),
            FieldMetadata(
                keyword="TAIMUTC_AT_TZERO",
                units="s",
            ),
        ] = None

        next_leap_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Epoch of next leap second, specified as an absolute time tag."
                ),
            ),
            FieldMetadata(keyword="NEXT_LEAP_EPOCH"),
        ] = None

        next_leap_taimutc: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Difference (TAI - UTC,) in seconds after the next leap second "
                    "at NEXT_LEAP_EPOCH. [s] "
                    "Should be provided when NEXT_LEAP_EPOCH is supplied."
                ),
            ),
            FieldMetadata(
                keyword="NEXT_LEAP_TAIMUTC",
                units="s",
            ),
        ] = None

        ut1mutc_at_tzero: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Difference (UT1 - UTC,) in seconds as modeled by the originator "
                    "at EPOCH_TZERO. [s]"
                ),
            ),
            FieldMetadata(
                keyword="UT1MUTC_AT_TZERO",
                units="s",
            ),
        ] = None

        # Earth orientation / ephemeris sources
        eop_source: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Source and version of the originator's Earth Orientation Parameters "
                    "(including leap seconds, TAI - UT1, etc.,)."
                ),
            ),
            FieldMetadata(keyword="EOP_SOURCE"),
        ] = None

        interp_method_eop: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Method used to select or interpolate sequential EOP data. "
                    "Examples: PRECEDING_VALUE, NEAREST_NEIGHBOR, LINEAR, LAGRANGE_ORDER_5."
                ),
            ),
            FieldMetadata(keyword="INTERP_METHOD_EOP"),
        ] = None

        celestial_source: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Source and version of the originator's celestial body ephemeris data "
                    "used in the creation of this message."
                ),
            ),
            FieldMetadata(keyword="CELESTIAL_SOURCE"),
        ] = None

        @model_validator(mode="before")
        @classmethod
        def _apply_sclk_defaults(cls, data: Any) -> Any:
            if (
                isinstance(data, dict)
                and str(data.get("time_system", "")).upper() == "SCLK"
            ):
                data.setdefault("sclk_offset_at_epoch", 0.0)
                data.setdefault("sclk_sec_per_si_sec", 1.0)
            return data

    # -----------------------------------------------------------------------
    # Trajectory State Time History (table 6-4)
    # -----------------------------------------------------------------------

    class TrajectoryStateTimeHistory(BaseModel):
        """
        Trajectory state time history block (TRAJ_START / TRAJ_STOP, 6.2.5).

        TRAJ_TYPE and CENTER_NAME are mandatory (table 6-4).
        TRAJ_REF_FRAME is mandatory (table 6-4).

        TRAJ_FRAME_EPOCH is conditional: required when the epoch is not intrinsic
        to the reference frame definition. The default value is EPOCH_TZERO (i.e.,
        if the frame epoch matches EPOCH_TZERO, this keyword may be omitted).
        Because TRAJ_REF_FRAME is a free-text SANA registry value, epoch-intrinsic
        determination is left to the application layer.

        ORB_REVNUM_BASIS is conditional: shall be provided when ORB_REVNUM is
        specified.

        ORB_AVERAGING is conditional: required when TRAJ_TYPE specifies orbital
        elements (not Cartesian or spherical); left to the application layer since
        TRAJ_TYPE is free-text.

        INTERPOLATION_DEGREE is conditional: must be provided when INTERPOLATION
        is set and not equal to 'PROPAGATE' (table 6-4, 6.2.5).

        data_lines contains the raw trajectory state lines as specified by TRAJ_TYPE.
        At least one data line is required (table 6-4: '...<Insert trajectory state
        time history here>' is marked M).
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("TRAJ_START", "TRAJ_STOP")
        _xml_tag: ClassVar[str] = "traj"
        _xml_line_tag: ClassVar[str] = "trajLine"

        comment: Comment = None

        traj_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Identification number for this trajectory state time history block.",
            ),
            FieldMetadata(keyword="TRAJ_ID"),
        ] = None

        traj_prev_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the previous trajectory state time history. "
                    "Omit if this is the first in a sequence."
                ),
            ),
            FieldMetadata(keyword="TRAJ_PREV_ID"),
        ] = None

        traj_next_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the next trajectory state time history. "
                    "Omit if this is the last in a sequence."
                ),
            ),
            FieldMetadata(keyword="TRAJ_NEXT_ID"),
        ] = None

        traj_basis: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Basis of this trajectory state time history data. "
                    "Suggested values: PREDICTED, DETERMINED, TELEMETRY, SIMULATED, OTHER."
                ),
            ),
            FieldMetadata(keyword="TRAJ_BASIS"),
        ] = None

        traj_basis_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the telemetry dataset, OD, navigation solution, "
                    "or simulation upon which this block is based. "
                    "Should match OD_ID when a matching OD block accompanies this trajectory."
                ),
            ),
            FieldMetadata(keyword="TRAJ_BASIS_ID"),
        ] = None

        interpolation: Annotated[
            Interpolation | str | None,
            Field(
                default=None,
                description=(
                    "Recommended interpolation method. Table 6-4 lists examples: HERMITE, "
                    "LAGRANGE, LINEAR, PROPAGATE; non-standard methods are accepted as plain "
                    "strings. INTERPOLATION_DEGREE must be provided if set to anything other "
                    "than PROPAGATE."
                ),
            ),
            FieldMetadata(keyword="INTERPOLATION"),
        ] = None

        interpolation_degree: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Recommended interpolation degree. Integer. Default 3. "
                    "Mandatory when INTERPOLATION is set and not 'PROPAGATE' (table 6-4,)."
                ),
            ),
            FieldMetadata(keyword="INTERPOLATION_DEGREE"),
        ] = None

        propagator: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name of the orbit propagator used to create this trajectory state time history. "
                    "Examples: HPOP, SP, SGP4."
                ),
            ),
            FieldMetadata(keyword="PROPAGATOR"),
        ] = None

        center_name: Annotated[
            CenterName | str,
            Field(
                description=(
                    "Origin of the orbit reference frame. May be a natural solar system body "
                    "(select from annex B, subsection B2, https://sanaregistry.org/r/orbit_centers,) "
                    "or another reference frame center such as a spacecraft or formation-flying "
                    "reference. Natural bodies resolve to CenterName enum members; other centers "
                    "are accepted as plain strings. Default EARTH (table 6-4)."
                ),
            ),
            FieldMetadata(keyword="CENTER_NAME"),
        ] = CenterName.EARTH

        traj_ref_frame: Annotated[
            RefFrame | str,
            Field(
                description=(
                    "Reference frame of the trajectory state time history. "
                    "Select from annex B, subsection B4 "
                    "(https://sanaregistry.org/r/celestial_body_reference_frames,). "
                    "Default ICRF3 (table 6-4). Parametric registry entries such as ICRFn and "
                    "ITRFyyyy are accepted via RefFrame.parametric(base, suffix). "
                    "Non-parametric B4 values not yet in the enum are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="TRAJ_REF_FRAME"),
        ] = RefFrame.parametric(RefFrame.ICRF, 3)

        traj_frame_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Epoch of the orbit data reference frame if not intrinsic to its definition. "
                    "Default EPOCH_TZERO. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="TRAJ_FRAME_EPOCH"),
        ] = None

        useable_start_time: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Start time of USEABLE time span covered by this ephemeris block. "
                    "Absolute or relative time tag. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="USEABLE_START_TIME"),
        ] = None

        useable_stop_time: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Stop time of USEABLE time span covered by this ephemeris block. "
                    "Absolute or relative time tag. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="USEABLE_STOP_TIME"),
        ] = None

        orb_revnum: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Integer orbit revolution number associated with the first trajectory "
                    "state in this block. If provided, ORB_REVNUM_BASIS shall also be provided."
                ),
            ),
            FieldMetadata(keyword="ORB_REVNUM"),
        ] = None

        orb_revnum_basis: Annotated[
            Literal[0, 1] | None,
            Field(
                default=None,
                description=(
                    "Basis for the orbit revolution counter (table 6-4,). "
                    "0 = first launch/deployment corresponds to revolution 0.XXXX; "
                    "1 = first launch/deployment corresponds to revolution 1.XXXX. "
                    "Default 0. Shall be provided when ORB_REVNUM is specified."
                ),
            ),
            FieldMetadata(keyword="ORB_REVNUM_BASIS"),
        ] = None

        traj_type: Annotated[
            OrbitalElements | str,
            Field(
                description=(
                    "Trajectory state type. Select from annex B, subsection B7 "
                    "(https://sanaregistry.org/r/orbital_elements,). Default CARTPV. "
                    "Non-standard values are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="TRAJ_TYPE"),
        ] = OrbitalElements.CARTPV

        orb_averaging: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Whether elements are osculating or mean, and if mean, which theory. "
                    "Select from annex B, subsection B13 "
                    "(https://sanaregistry.org/r/orbit_averaging,). "
                    "Examples: OSCULATING, BROUWER, KOZAI. Default OSCULATING. "
                    "Not required for Cartesian or spherical TRAJ_TYPEs."
                ),
            ),
            FieldMetadata(keyword="ORB_AVERAGING"),
        ] = None

        traj_units: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-delimited SI unit designations for each element of the trajectory "
                    "state following the time tag, for informational purposes only. "
                    "Enclosed in square brackets. Example: [km,km,km,km/s,km/s,km/s]. "
                    "Does not override mandatory SANA registry units for the selected TRAJ_TYPE."
                ),
            ),
            FieldMetadata(keyword="TRAJ_UNITS"),
        ] = None

        # The actual data lines (free-format, content determined by TRAJ_TYPE).
        # At least one line is required.
        data_lines: Annotated[
            list[str],
            Field(
                min_length=1,
                description=(
                    "Trajectory state time history lines, each beginning with an absolute "
                    "or relative time tag followed by trajectory state elements as specified "
                    "by TRAJ_TYPE. At least one record is required (6.2.5.11,). "
                    "Each line must be time-ordered (monotonically increasing) per 6.2.5.6."
                ),
            ),
        ]

        @field_validator("orb_revnum_basis", mode="before")
        @classmethod
        def coerce_orb_revnum_basis(cls, v: object) -> object:
            # KVN/XML readers always pass strings; coerce to int before Literal check.
            if isinstance(v, str):
                try:
                    return int(v)
                except ValueError:
                    raise ValueError("orb_revnum_basis must be 0 or 1") from None
            return v

        @model_validator(mode="before")
        @classmethod
        def _apply_interpolation_degree_default(cls, data: Any) -> Any:
            if isinstance(data, dict):
                interp = str(data.get("interpolation", "")).upper()
                if (
                    interp
                    and interp != "PROPAGATE"
                    and data.get("interpolation_degree") is None
                ):
                    data["interpolation_degree"] = 3
            return data

        @model_validator(mode="before")
        @classmethod
        def _apply_orb_revnum_basis_default(cls, data: Any) -> Any:
            if isinstance(data, dict) and (
                data.get("orb_revnum") is not None
                and data.get("orb_revnum_basis") is None
            ):
                data["orb_revnum_basis"] = 0
            return data

        @model_validator(mode="after")
        def _validate_orb_averaging_required(self) -> OCM.TrajectoryStateTimeHistory:
            _cartesian_or_spherical: frozenset[str] = frozenset(
                {"CARTP", "CARTPV", "CARTPVA", "LDBARV", "ADBARV", "GEODETIC"}
            )
            if (
                str(self.traj_type).upper() not in _cartesian_or_spherical
                and self.orb_averaging is None
            ):
                raise ValueError(
                    f"orb_averaging is required when traj_type='{self.traj_type}' "
                    "(non-Cartesian/spherical element type, table 6-4)."
                )
            return self

        @model_validator(mode="before")
        @classmethod
        def _apply_orb_averaging_default(cls, data: Any) -> Any:
            _cartesian_or_spherical: frozenset[str] = frozenset(
                {"CARTP", "CARTPV", "CARTPVA", "LDBARV", "ADBARV", "GEODETIC"}
            )
            if isinstance(data, dict):
                traj_type = str(data.get("traj_type", "")).upper()
                if traj_type and traj_type not in _cartesian_or_spherical:
                    data.setdefault("orb_averaging", "OSCULATING")
            return data

        @field_validator("traj_units")
        @classmethod
        def _validate_traj_units_brackets(cls, v: str | None) -> str | None:
            if v is not None and not (v.startswith("[") and v.endswith("]")):
                raise ValueError(
                    f"traj_units must be enclosed in square brackets "
                    f"(e.g. '[km,km,km,km/s,km/s,km/s]'), got {v!r} (table 6-4)."
                )
            return v

        @model_validator(mode="after")
        def validate_data_lines_ordered(self) -> OCM.TrajectoryStateTimeHistory:
            """Validate trajectory state time history is strictly ordered (section 6.2.5.6, section 6.2.2.4)."""
            _check_data_lines_ordered(self.data_lines, "trajectory state")
            return self

    # -----------------------------------------------------------------------
    # Physical Properties (table 6-5)
    # -----------------------------------------------------------------------

    class SpaceObjectPhysicalCharacteristics(BaseModel):
        """
        Space object physical characteristics block (PHYS_START / PHYS_STOP, 6.2.6.2).

        All fields are optional except the delimiters.

        OEB_PARENT_FRAME is conditional: shall be provided if OEB_Q1/Q2/Q3/QC
        are specified.
        OEB_PARENT_FRAME_EPOCH is conditional: required when OEB_PARENT_FRAME
        is provided and its epoch is not intrinsic to the frame definition.
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("PHYS_START", "PHYS_STOP")
        _xml_tag: ClassVar[str] = "phys"

        comment: Comment = None

        manufacturer: Annotated[
            str | None,
            Field(
                default=None,
                description="Satellite manufacturer's name.",
            ),
            FieldMetadata(keyword="MANUFACTURER"),
        ] = None

        bus_model: Annotated[
            str | None,
            Field(
                default=None,
                description="Satellite manufacturer's spacecraft bus model name.",
            ),
            FieldMetadata(keyword="BUS_MODEL"),
        ] = None

        docked_with: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-separated list of other space objects this object is docked to."
                ),
            ),
            FieldMetadata(keyword="DOCKED_WITH"),
        ] = None

        drag_const_area: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-independent drag cross-sectional area (AD,) facing the relative "
                    "wind vector, not included in AREA_ALONG_OEB parameters. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="DRAG_CONST_AREA",
                units="m**2",
            ),
        ] = None

        drag_coeff_nom: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Nominal drag coefficient (CD_NOM,). If 0, no atmospheric drag considered."
                ),
            ),
            FieldMetadata(keyword="DRAG_COEFF_NOM"),
        ] = None

        drag_uncertainty: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Drag coefficient 1-sigma percent uncertainty. [%] "
                    "Actual 1-sigma range = (1.0 +/- DRAG_UNCERTAINTY/100.0,) * CD_NOM."
                ),
            ),
            FieldMetadata(
                keyword="DRAG_UNCERTAINTY",
                units="%",
            ),
        ] = None

        initial_wet_mass: Annotated[
            float | None,
            Field(
                default=None,
                description="Space object total mass at beginning of life. [kg]",
            ),
            FieldMetadata(
                keyword="INITIAL_WET_MASS",
                units="kg",
            ),
        ] = None

        wet_mass: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Space object total mass including propellant at EPOCH_TZERO. [kg]"
                ),
            ),
            FieldMetadata(
                keyword="WET_MASS",
                units="kg",
            ),
        ] = None

        dry_mass: Annotated[
            float | None,
            Field(
                default=None,
                description="Space object dry mass without propellant. [kg]",
            ),
            FieldMetadata(
                keyword="DRY_MASS",
                units="kg",
            ),
        ] = None

        # OEB frame and quaternion parameters
        oeb_parent_frame: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Parent reference frame mapped to the OEB frame via the quaternion "
                    "transformation defined in annex F. Select from annex B, subsections B4 and B5. "
                    "Shall be provided if OEB_Q1/Q2/Q3/QC are specified."
                ),
            ),
            FieldMetadata(keyword="OEB_PARENT_FRAME", spec_default="RSW_ROTATING"),
        ] = None

        oeb_parent_frame_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Epoch of the OEB parent frame if not intrinsic to the frame definition. "
                    "Default EPOCH_TZERO. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="OEB_PARENT_FRAME_EPOCH"),
        ] = None

        oeb_q1: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "q1 = e1 * sin(phi/2,) for rotation from OEB_PARENT_FRAME to OEB frame. "
                    "A value of -999 denotes a tumbling space object."
                ),
            ),
            FieldMetadata(keyword="OEB_Q1"),
        ] = None

        oeb_q2: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "q2 = e2 * sin(phi/2,) for rotation from OEB_PARENT_FRAME to OEB frame. "
                    "A value of -999 denotes a tumbling space object."
                ),
            ),
            FieldMetadata(keyword="OEB_Q2"),
        ] = None

        oeb_q3: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "q3 = e3 * sin(phi/2,) for rotation from OEB_PARENT_FRAME to OEB frame. "
                    "A value of -999 denotes a tumbling space object."
                ),
            ),
            FieldMetadata(keyword="OEB_Q3"),
        ] = None

        oeb_qc: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "qc = cos(phi/2,) for rotation from OEB_PARENT_FRAME to OEB frame. "
                    "Made non-negative by convention. "
                    "A value of -999 denotes a tumbling space object."
                ),
            ),
            FieldMetadata(keyword="OEB_QC"),
        ] = None

        # OEB physical dimensions
        oeb_max: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum physical dimension (along X_OEB,) of the OEB. [m]",
            ),
            FieldMetadata(
                keyword="OEB_MAX",
                units="m",
            ),
        ] = None

        oeb_int: Annotated[
            float | None,
            Field(
                default=None,
                description="Intermediate physical dimension (along y_OEB,) of OEB. [m]",
            ),
            FieldMetadata(
                keyword="OEB_INT",
                units="m",
            ),
        ] = None

        oeb_min: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum physical dimension (along z_OEB,) of OEB. [m]",
            ),
            FieldMetadata(
                keyword="OEB_MIN",
                units="m",
            ),
        ] = None

        # Attitude-dependent cross-sectional areas
        area_along_oeb_max: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-dependent cross-sectional area when viewed along max OEB (X_OEB,). "
                    "Not included in DRAG_CONST_AREA or SRP_CONST_AREA. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="AREA_ALONG_OEB_MAX",
                units="m**2",
            ),
        ] = None

        area_along_oeb_int: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-dependent cross-sectional area when viewed along intermediate "
                    "OEB (y_OEB,). Not included in DRAG_CONST_AREA or SRP_CONST_AREA. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="AREA_ALONG_OEB_INT",
                units="m**2",
            ),
        ] = None

        area_along_oeb_min: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-dependent cross-sectional area when viewed along minimum "
                    "OEB (z_OEB,). Not included in DRAG_CONST_AREA or SRP_CONST_AREA. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="AREA_ALONG_OEB_MIN",
                units="m**2",
            ),
        ] = None

        # Collision probability areas
        area_min_for_pc: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum cross-sectional area for collision probability estimation. [m**2]",
            ),
            FieldMetadata(
                keyword="AREA_MIN_FOR_PC",
                units="m**2",
            ),
        ] = None

        area_max_for_pc: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum cross-sectional area for collision probability estimation. [m**2]",
            ),
            FieldMetadata(
                keyword="AREA_MAX_FOR_PC",
                units="m**2",
            ),
        ] = None

        area_typ_for_pc: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile,) cross-sectional area sampled over all orientations "
                    "for collision probability estimation. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="AREA_TYP_FOR_PC",
                units="m**2",
            ),
        ] = None

        # Radar cross section
        rcs: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile,) effective Radar Cross Section sampled over all "
                    "viewing angles. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="RCS",
                units="m**2",
            ),
        ] = None

        rcs_min: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum Radar Cross Section observed for this object. [m**2]",
            ),
            FieldMetadata(
                keyword="RCS_MIN",
                units="m**2",
            ),
        ] = None

        rcs_max: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum Radar Cross Section observed for this object. [m**2]",
            ),
            FieldMetadata(
                keyword="RCS_MAX",
                units="m**2",
            ),
        ] = None

        # Solar radiation pressure
        srp_const_area: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-independent solar radiation pressure cross-sectional area (AR,) "
                    "facing the Sun, not included in AREA_ALONG_OEB parameters. [m**2]"
                ),
            ),
            FieldMetadata(
                keyword="SRP_CONST_AREA",
                units="m**2",
            ),
        ] = None

        solar_rad_coeff: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Nominal Solar Radiation Pressure Coefficient (CR_NOM,). "
                    "If 0, no solar radiation pressure considered."
                ),
            ),
            FieldMetadata(keyword="SOLAR_RAD_COEFF"),
        ] = None

        solar_rad_uncertainty: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "SRP 1-sigma percent uncertainty. [%] "
                    "Actual 1-sigma range = (1.0 +/- SRP_UNCERTAINTY/100.0,) * CR_NOM."
                ),
            ),
            FieldMetadata(
                keyword="SOLAR_RAD_UNCERTAINTY",
                units="%",
            ),
        ] = None

        # Visual magnitude
        vm_absolute: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile,) absolute Visual Magnitude normalized to 1 AU "
                    "Sun-to-target, 0 deg phase angle, 40,000 km target-to-sensor distance."
                ),
            ),
            FieldMetadata(keyword="VM_ABSOLUTE"),
        ] = None

        vm_apparent_min: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum apparent Visual Magnitude observed for this space object.",
            ),
            FieldMetadata(keyword="VM_APPARENT_MIN"),
        ] = None

        vm_apparent: Annotated[
            float | None,
            Field(
                default=None,
                description="Typical (50th percentile,) apparent Visual Magnitude observed.",
            ),
            FieldMetadata(keyword="VM_APPARENT"),
        ] = None

        vm_apparent_max: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Maximum apparent Visual Magnitude observed (the lowest Vmag = brightest,)."
                ),
            ),
            FieldMetadata(keyword="VM_APPARENT_MAX"),
        ] = None

        reflectance: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                le=1,
                description=(
                    "Typical (50th percentile,) coefficient of reflectance over all viewing "
                    "angles, ranging from 0 (none) to 1 (perfect reflectance)."
                ),
            ),
            FieldMetadata(keyword="REFLECTANCE"),
        ] = None

        # Attitude control
        att_control_mode: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Primary mode of attitude control. "
                    "Examples: THREE_AXIS, SPIN, DUAL_SPIN, TUMBLING, "
                    "GRAVITY_GRADIENT."
                ),
            ),
            FieldMetadata(keyword="ATT_CONTROL_MODE"),
        ] = None

        att_actuator_type: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Type of actuator for attitude control. "
                    "Examples: ATT_THRUSTERS, ACTIVE_MAG_TORQUE, PASSIVE_MAG_TORQUE, "
                    "REACTION_WHEELS, MOMENTUM_WHEELS, CONTROL_MOMENT_GYROSCOPE, NONE, OTHER."
                ),
            ),
            FieldMetadata(keyword="ATT_ACTUATOR_TYPE"),
        ] = None

        att_knowledge: Annotated[
            float | None,
            Field(
                default=None,
                description="Accuracy of attitude knowledge. [deg]",
            ),
            FieldMetadata(
                keyword="ATT_KNOWLEDGE",
                units="deg",
            ),
        ] = None

        att_control: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Accuracy of attitude control system to maintain attitude assuming "
                    "perfect knowledge (deadbands,). [deg]"
                ),
            ),
            FieldMetadata(
                keyword="ATT_CONTROL",
                units="deg",
            ),
        ] = None

        att_pointing: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Overall accuracy of spacecraft to maintain attitude including knowledge "
                    "errors and ACS operation. [deg]"
                ),
            ),
            FieldMetadata(
                keyword="ATT_POINTING",
                units="deg",
            ),
        ] = None

        # Maneuver capability
        avg_maneuver_freq: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Average maneuver frequency (number of orbit- or attitude-adjust "
                    "maneuvers per year,). [#/yr]"
                ),
            ),
            FieldMetadata(
                keyword="AVG_MANEUVER_FREQ",
                units="#/yr",
            ),
        ] = None

        max_thrust: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Maximum composite thrust in any single body-fixed direction. [N]"
                ),
            ),
            FieldMetadata(
                keyword="MAX_THRUST",
                units="N",
            ),
        ] = None

        dv_bol: Annotated[
            float | None,
            Field(
                default=None,
                description="Total delta-V capability at beginning of life. [km/s]",
            ),
            FieldMetadata(
                keyword="DV_BOL",
                units="km/s",
            ),
        ] = None

        dv_remaining: Annotated[
            float | None,
            Field(
                default=None,
                description="Total delta-V remaining for the spacecraft. [km/s]",
            ),
            FieldMetadata(
                keyword="DV_REMAINING",
                units="km/s",
            ),
        ] = None

        # Moments of inertia
        ixx: Annotated[
            float | None,
            Field(
                default=None,
                description="Moment of inertia about the X-axis of the primary body frame. [kg*m**2]",
            ),
            FieldMetadata(
                keyword="IXX",
                units="kg*m**2",
            ),
        ] = None

        iyy: Annotated[
            float | None,
            Field(
                default=None,
                description="Moment of inertia about the Y-axis. [kg*m**2]",
            ),
            FieldMetadata(
                keyword="IYY",
                units="kg*m**2",
            ),
        ] = None

        izz: Annotated[
            float | None,
            Field(
                default=None,
                description="Moment of inertia about the Z-axis. [kg*m**2]",
            ),
            FieldMetadata(
                keyword="IZZ",
                units="kg*m**2",
            ),
        ] = None

        ixy: Annotated[
            float | None,
            Field(
                default=None,
                description="Inertia cross product of the X & Y axes. [kg*m**2]",
            ),
            FieldMetadata(
                keyword="IXY",
                units="kg*m**2",
            ),
        ] = None

        ixz: Annotated[
            float | None,
            Field(
                default=None,
                description="Inertia cross product of the X & Z axes. [kg*m**2]",
            ),
            FieldMetadata(
                keyword="IXZ",
                units="kg*m**2",
            ),
        ] = None

        iyz: Annotated[
            float | None,
            Field(
                default=None,
                description="Inertia cross product of the Y & Z axes. [kg*m**2]",
            ),
            FieldMetadata(
                keyword="IYZ",
                units="kg*m**2",
            ),
        ] = None

        @field_validator("oeb_qc")
        @classmethod
        def _validate_oeb_qc(cls, v: float | None) -> float | None:
            if v is not None and v < 0 and v != -999.0:
                raise ValueError(
                    f"oeb_qc must be non-negative by convention, or -999 for a tumbling "
                    f"space object (table 6-5), got {v}."
                )
            return v

        @model_validator(mode="after")
        def _validate_oeb_tumbling_consistency(
            self,
        ) -> OCM.SpaceObjectPhysicalCharacteristics:
            qs = [self.oeb_q1, self.oeb_q2, self.oeb_q3, self.oeb_qc]
            sentinels = [q == -999.0 for q in qs if q is not None]
            if sentinels and any(sentinels) and not all(sentinels):
                raise ValueError(
                    "OEB_Q1/Q2/Q3/QC tumbling sentinel (-999) must be consistent: "
                    "all four must be -999, or none should be (table 6-5)."
                )
            return self

        @model_validator(mode="after")
        def _validate_oeb_parent_frame_epoch_copresence(
            self,
        ) -> OCM.SpaceObjectPhysicalCharacteristics:
            qs = [self.oeb_q1, self.oeb_q2, self.oeb_q3, self.oeb_qc]
            frame_active = self.oeb_parent_frame is not None or any(
                q is not None for q in qs
            )
            if self.oeb_parent_frame_epoch is not None and not frame_active:
                raise ValueError(
                    "oeb_parent_frame_epoch requires oeb_parent_frame to be set "
                    "or OEB_Q values to be present (table 6-5)."
                )
            return self

        @model_validator(mode="before")
        @classmethod
        def _default_oeb_parent_frame(cls, data: Any) -> Any:
            # Spec table 6-5 note: OEB_PARENT_FRAME is mandatory when quaternions are
            # provided, but defaults to RSW_ROTATING when omitted. Supply the default so
            # files that rely on this convention (e.g. annex G-16) parse correctly.
            if not isinstance(data, dict):
                return data
            q_fields = ("oeb_q1", "oeb_q2", "oeb_q3", "oeb_qc")
            q_vals = [data.get(q) for q in q_fields]
            if (
                not any(v is not None for v in q_vals)
                or data.get("oeb_parent_frame") is not None
            ):
                return data
            try:
                present = [float(v) for v in q_vals if v is not None]
                if all(f == -999.0 for f in present):
                    return data  # tumbling sentinel: parent frame is N/A
            except (TypeError, ValueError):
                pass
            data = dict(data)
            data["oeb_parent_frame"] = "RSW_ROTATING"
            return data

        @model_validator(mode="after")
        def _validate_oeb_parent_frame_required(
            self,
        ) -> OCM.SpaceObjectPhysicalCharacteristics:
            qs = [self.oeb_q1, self.oeb_q2, self.oeb_q3, self.oeb_qc]
            non_none = [q for q in qs if q is not None]
            # Tumbling sentinel (all -999) means no defined orientation; parent frame is N/A.
            if (
                non_none
                and self.oeb_parent_frame is None
                and not all(q == -999.0 for q in non_none)
            ):
                raise ValueError(
                    "oeb_parent_frame is required when OEB_Q1/Q2/Q3/QC are specified (table 6-5)."
                )
            return self

    # -----------------------------------------------------------------------
    # Covariance Time History (table 6-6)
    # -----------------------------------------------------------------------

    class CovarianceTimeHistory(BaseModel):
        """
        Covariance time history block (COV_START / COV_STOP, 6.2.7).

        COV_REF_FRAME, COV_TYPE, and COV_ORDERING are mandatory (table 6-6).

        COV_FRAME_EPOCH is conditional: required when the epoch is not intrinsic
        to the reference frame definition. The default is EPOCH_TZERO.

        data_lines contains the raw covariance lines as specified by COV_TYPE
        and COV_ORDERING. At least one data line is required (table 6-6).
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("COV_START", "COV_STOP")
        _xml_tag: ClassVar[str] = "cov"
        _xml_line_tag: ClassVar[str] = "covLine"

        comment: Comment = None

        cov_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Identification number for this covariance time history block.",
            ),
            FieldMetadata(keyword="COV_ID"),
        ] = None

        cov_prev_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the previous covariance time history. "
                    "Omit if this is the first in a sequence."
                ),
            ),
            FieldMetadata(keyword="COV_PREV_ID"),
        ] = None

        cov_next_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the next covariance time history. "
                    "Omit if this is the last in a sequence."
                ),
            ),
            FieldMetadata(keyword="COV_NEXT_ID"),
        ] = None

        cov_basis: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Basis of this covariance time history data. "
                    "Suggested values: PREDICTED, EMPIRICAL, DETERMINED, SIMULATED, OTHER."
                ),
            ),
            FieldMetadata(keyword="COV_BASIS"),
        ] = None

        cov_basis_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the OD, navigation solution, or simulation "
                    "upon which this covariance block is based. "
                    "Should match OD_ID when a matching OD block is present."
                ),
            ),
            FieldMetadata(keyword="COV_BASIS_ID"),
        ] = None

        cov_ref_frame: Annotated[
            RefFrame | ExtendedManCovRefFrame | str,
            Field(
                description=(
                    "Reference frame of the covariance time history. "
                    "Select from annex B, subsections B4 and B5 "
                    "(https://sanaregistry.org/r/celestial_body_reference_frames, "
                    "https://sanaregistry.org/r/orbit_relative_reference_frames,). "
                    "Default TNW_INERTIAL. Non-standard frames are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="COV_REF_FRAME"),
        ] = ExtendedManCovRefFrame.TNW_INERTIAL

        cov_frame_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Epoch of the covariance data reference frame if not intrinsic to the "
                    "frame definition. Default EPOCH_TZERO. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="COV_FRAME_EPOCH"),
        ] = None

        cov_scale_min: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum scale factor to apply to this covariance data to achieve realism.",
            ),
            FieldMetadata(keyword="COV_SCALE_MIN"),
        ] = None

        cov_scale_max: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum scale factor to apply to this covariance data to achieve realism.",
            ),
            FieldMetadata(keyword="COV_SCALE_MAX"),
        ] = None

        cov_confidence: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Measure of confidence in the covariance errors matching reality. [%] "
                    "Characterized via Wald test, Chi-squared test, log of likelihood, or "
                    "numeric per mutual agreement."
                ),
            ),
            FieldMetadata(
                keyword="COV_CONFIDENCE",
                units="%",
            ),
        ] = None

        cov_type: Annotated[
            OrbitalElements | CovarianceType | str,
            Field(
                description=(
                    "Covariance composition type. Select from SANA Registry of Orbital Elements "
                    "(annex B, subsection B7,) or Covariance Representations (annex B, subsection B8). "
                    "Default CARTPV. Non-standard values are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="COV_TYPE"),
        ] = OrbitalElements.CARTPV

        cov_ordering: Annotated[
            CovarianceOrdering,
            Field(
                description=(
                    "Covariance element ordering. One of: LTM (lower triangular matrix), "
                    "UTM (upper triangular matrix), FULL (full symmetric matrix), "
                    "LTMWCC (LTM with cross-correlations in upper off-diagonal), "
                    "UTMWCC (UTM with cross-correlations in lower off-diagonal). Default LTM."
                ),
            ),
            FieldMetadata(keyword="COV_ORDERING"),
        ] = CovarianceOrdering.LTM

        cov_units: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-delimited SI unit designations for each element of the covariance "
                    "following the time tag, for informational purposes only. "
                    "Enclosed in square brackets. Corresponds to standard deviations of diagonal "
                    "elements. Does not override mandatory SANA registry units for COV_TYPE."
                ),
            ),
            FieldMetadata(keyword="COV_UNITS"),
        ] = None

        # Raw covariance data lines; at least one is required.
        data_lines: Annotated[
            list[str],
            Field(
                min_length=1,
                description=(
                    "Covariance time history lines, each beginning with an absolute or "
                    "relative time tag followed by covariance matrix elements as specified by "
                    "COV_TYPE and COV_ORDERING. At least one line is required (6.2.7.11b,)."
                ),
            ),
        ]

        @field_validator("cov_units")
        @classmethod
        def _validate_cov_units_brackets(cls, v: str | None) -> str | None:
            if v is not None and not (v.startswith("[") and v.endswith("]")):
                raise ValueError(
                    f"cov_units must be enclosed in square brackets "
                    f"(e.g. '[km,km/s]'), got {v!r} (table 6-6)."
                )
            return v

        @model_validator(mode="after")
        def _validate_cov_scale_order(self) -> OCM.CovarianceTimeHistory:
            if (
                self.cov_scale_min is not None
                and self.cov_scale_max is not None
                and self.cov_scale_min > self.cov_scale_max
            ):
                raise ValueError(
                    f"cov_scale_min ({self.cov_scale_min}) must be <= "
                    f"cov_scale_max ({self.cov_scale_max}) (table 6-6)."
                )
            return self

        @model_validator(mode="after")
        def validate_data_lines_ordered(self) -> OCM.CovarianceTimeHistory:
            """Validate covariance time history is strictly ordered (section 6.2.7.6, section 6.2.2.4)."""
            _check_data_lines_ordered(self.data_lines, "covariance")
            return self

    # -----------------------------------------------------------------------
    # Maneuver Specification (tables 6-7, 6-8, 6-9)
    # -----------------------------------------------------------------------

    class ManeuverSpecification(BaseModel):
        """
        Maneuver time history block (MAN_START / MAN_STOP, 6.2.8).

        MAN_ID, MAN_DEVICE_ID, MAN_REF_FRAME, DC_TYPE, and MAN_COMPOSITION
        are mandatory (table 6-7).

        MAN_FRAME_EPOCH is conditional: required when the epoch is not intrinsic
        to the reference frame definition.

        DC duty cycle fields are conditional on DC_TYPE (6.2.8.20.6-6.2.8.20.7):

        - DC_WIN_OPEN, DC_WIN_CLOSE, DC_EXEC_START, DC_EXEC_STOP, DC_REF_TIME,
          DC_TIME_PULSE_DURATION, DC_TIME_PULSE_PERIOD shall all be set when
          DC_TYPE is not 'CONTINUOUS'.
        - DC_REF_DIR, DC_BODY_FRAME, DC_BODY_TRIGGER, DC_PA_START_ANGLE,
          DC_PA_STOP_ANGLE additionally required when DC_TYPE is 'TIME_AND_ANGLE'.

        data_lines contains the raw maneuver lines as specified by MAN_COMPOSITION.
        At least one data line is required.

        Note on DC_REF_DIR and DC_BODY_TRIGGER: these are three-element space-delimited
        vectors. Per 7.6 they are stored as single strings (the three numbers on one line).
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("MAN_START", "MAN_STOP")
        _xml_tag: ClassVar[str] = "man"
        _xml_line_tag: ClassVar[str] = "manLine"

        class ManeuverDataLine(BaseModel):
            """
            One typed propulsive maneuver data line (table 6-8).

            A read-only view over a raw ``data_lines`` entry, built by
            ``parsed_data_lines()``. Each field carries its CCSDS ``FieldMetadata``
            keyword, so the parser maps MAN_COMPOSITION columns to fields by
            introspection - not by hardcoded names. The single time column
            (TIME_ABSOLUTE or TIME_RELATIVE) maps to ``time_tag``. Only columns named
            in MAN_COMPOSITION are populated. The two spec ``shall`` constraints are
            enforced here: THR_INTERP is 'ON'/'OFF' (table 6-8); ACC_INTERP shares
            that on/off domain (the table lists only those values).
            """

            model_config = CCSDS_MODEL_CONFIG

            time_tag: str
            man_dura: Annotated[float | None, FieldMetadata("MAN_DURA", units="s")] = None
            delta_mass: Annotated[
                float | None, FieldMetadata("DELTA_MASS", units="kg")
            ] = None
            acc_x: Annotated[float | None, FieldMetadata("ACC_X", units="km/s**2")] = None
            acc_y: Annotated[float | None, FieldMetadata("ACC_Y", units="km/s**2")] = None
            acc_z: Annotated[float | None, FieldMetadata("ACC_Z", units="km/s**2")] = None
            acc_interp: Annotated[
                Literal["ON", "OFF"] | None, FieldMetadata("ACC_INTERP")
            ] = None
            acc_mag_sigma: Annotated[
                float | None, FieldMetadata("ACC_MAG_SIGMA", units="%")
            ] = None
            acc_dir_sigma: Annotated[
                float | None, FieldMetadata("ACC_DIR_SIGMA", units="deg")
            ] = None
            dv_x: Annotated[float | None, FieldMetadata("DV_X", units="km/s")] = None
            dv_y: Annotated[float | None, FieldMetadata("DV_Y", units="km/s")] = None
            dv_z: Annotated[float | None, FieldMetadata("DV_Z", units="km/s")] = None
            dv_mag_sigma: Annotated[
                float | None, FieldMetadata("DV_MAG_SIGMA", units="%")
            ] = None
            dv_dir_sigma: Annotated[
                float | None, FieldMetadata("DV_DIR_SIGMA", units="deg")
            ] = None
            thr_x: Annotated[float | None, FieldMetadata("THR_X", units="N")] = None
            thr_y: Annotated[float | None, FieldMetadata("THR_Y", units="N")] = None
            thr_z: Annotated[float | None, FieldMetadata("THR_Z", units="N")] = None
            thr_effic: Annotated[float | None, FieldMetadata("THR_EFFIC")] = None
            thr_interp: Annotated[
                Literal["ON", "OFF"] | None, FieldMetadata("THR_INTERP")
            ] = None
            thr_isp: Annotated[float | None, FieldMetadata("THR_ISP", units="s")] = None
            isp: Annotated[float | None, FieldMetadata("ISP", units="s")] = None
            thr_mag_sigma: Annotated[
                float | None, FieldMetadata("THR_MAG_SIGMA", units="%")
            ] = None
            thr_dir_sigma: Annotated[
                float | None, FieldMetadata("THR_DIR_SIGMA", units="deg")
            ] = None

        class DeploymentDataLine(BaseModel):
            """
            One typed deployment maneuver data line (table 6-9).

            Read-only view built by ``parsed_data_lines()``; see ``ManeuverDataLine``
            for the FieldMetadata-driven field convention. The spec ``shall``
            constraint DEPLOY_MASS <= 0.0 (a decrement in host mass) is enforced
            here. DEPLOY_ID is free text; the value ``0`` denotes "no deployment".
            """

            model_config = CCSDS_MODEL_CONFIG

            time_tag: str
            deploy_id: Annotated[str | None, FieldMetadata("DEPLOY_ID")] = None
            deploy_dv_x: Annotated[
                float | None, FieldMetadata("DEPLOY_DV_X", units="km/s")
            ] = None
            deploy_dv_y: Annotated[
                float | None, FieldMetadata("DEPLOY_DV_Y", units="km/s")
            ] = None
            deploy_dv_z: Annotated[
                float | None, FieldMetadata("DEPLOY_DV_Z", units="km/s")
            ] = None
            deploy_mass: Annotated[
                float | None, Field(le=0.0), FieldMetadata("DEPLOY_MASS", units="kg")
            ] = None
            deploy_dv_sigma: Annotated[
                float | None, FieldMetadata("DEPLOY_DV_SIGMA", units="%")
            ] = None
            deploy_dir_sigma: Annotated[
                float | None, FieldMetadata("DEPLOY_DIR_SIGMA", units="deg")
            ] = None
            deploy_dv_ratio: Annotated[float | None, FieldMetadata("DEPLOY_DV_RATIO")] = (
                None
            )
            deploy_dv_cda: Annotated[
                float | None, FieldMetadata("DEPLOY_DV_CDA", units="m**2")
            ] = None

        comment: Comment = None

        man_id: Annotated[
            str,
            Field(
                description=(
                    "Unique maneuver identification number for this maneuver. "
                    "All supplied maneuver constituents with the same MAN_BASIS and "
                    "MAN_REF_FRAME shall be added together for the total composite maneuver."
                ),
            ),
            FieldMetadata(keyword="MAN_ID"),
        ]

        man_prev_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number of the previous maneuver for this MAN_BASIS. "
                    "Omit if this is the first in a sequence."
                ),
            ),
            FieldMetadata(keyword="MAN_PREV_ID"),
        ] = None

        man_next_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number of the next maneuver for this MAN_BASIS. "
                    "Omit if this is the last in a sequence."
                ),
            ),
            FieldMetadata(keyword="MAN_NEXT_ID"),
        ] = None

        man_basis: Annotated[
            ManeuverBasis | None,
            Field(
                default=None,
                description=(
                    "Basis of this maneuver time history data (section 6.2.8, table 6-7,). "
                    "One of: CANDIDATE, PLANNED, ANTICIPATED, TELEMETRY, "
                    "DETERMINED, SIMULATED, OTHER."
                ),
            ),
            FieldMetadata(keyword="MAN_BASIS"),
        ] = None

        man_basis_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the OD, navigation solution, or simulation "
                    "upon which this maneuver block is based. "
                    "Should match OD_ID when a matching OD block is present."
                ),
            ),
            FieldMetadata(keyword="MAN_BASIS_ID"),
        ] = None

        man_device_id: Annotated[
            str,
            Field(
                description=(
                    "Maneuver device identifier. 'ALL' = summed acceleration/delta-V/thrust of "
                    "any/all thrusters. 'DEPLOY' = maneuvers caused by deployments only. "
                    "Otherwise: free-text identifier for the specific thruster/device."
                ),
            ),
            FieldMetadata(keyword="MAN_DEVICE_ID"),
        ]

        man_prev_epoch: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Completion time of the previous maneuver for this MAN_BASIS. "
                    "Absolute or relative time tag."
                ),
            ),
            FieldMetadata(keyword="MAN_PREV_EPOCH"),
        ] = None

        man_next_epoch: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Start time of the next maneuver for this MAN_BASIS. "
                    "Absolute or relative time tag."
                ),
            ),
            FieldMetadata(keyword="MAN_NEXT_EPOCH"),
        ] = None

        man_purpose: Annotated[
            ManeuverPurpose | str | None,
            Field(
                default=None,
                description=(
                    "Intention(s,) of the maneuver as a comma-delimited list. "
                    "Examples: DISPOSAL, COLA, ORBIT, SK, RELOCATION, LEOP, DEPLOY, "
                    "INCLINATION, PERIOD, TRIM, SCI_OBJ, DESAT, OTHER."
                ),
            ),
            FieldMetadata(keyword="MAN_PURPOSE"),
        ] = None

        man_pred_source: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "For future maneuvers, source of the orbit and/or attitude state(s,) "
                    "upon which the maneuver is based. Free-text; consider TRAJ_ID or OD_ID."
                ),
            ),
            FieldMetadata(keyword="MAN_PRED_SOURCE"),
        ] = None

        man_ref_frame: Annotated[
            RefFrame | ExtendedManCovRefFrame | str,
            Field(
                description=(
                    "Reference frame in which all maneuver vector direction data is provided. "
                    "Select from annex B, subsections B4 and B5. "
                    "Must be the same for all data elements within this block. "
                    "Default TNW_INERTIAL (table 6-7). "
                    "Non-standard frames are accepted as plain strings."
                ),
            ),
            FieldMetadata(
                keyword="MAN_REF_FRAME", spec_default=ExtendedManCovRefFrame.TNW_INERTIAL
            ),
        ] = ExtendedManCovRefFrame.TNW_INERTIAL

        man_frame_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Epoch of the maneuver data reference frame if not intrinsic to the "
                    "frame definition. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="MAN_FRAME_EPOCH"),
        ] = None

        grav_assist_name: Annotated[
            CenterName | str | None,
            Field(
                default=None,
                description=(
                    "Origin of maneuver gravitational assist body. "
                    "Select from annex B, subsection B2 "
                    "(https://sanaregistry.org/r/orbit_centers,). "
                    "Non-standard centers are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="GRAV_ASSIST_NAME"),
        ] = None

        dc_type: Annotated[
            DutyCycleType,
            Field(
                description=(
                    "Duty cycle type. One of: CONTINUOUS (default), TIME, TIME_AND_ANGLE. "
                    "If not CONTINUOUS, duty cycle fields are required (6.2.8.20.6-6.2.8.20.7)."
                ),
            ),
            FieldMetadata(keyword="DC_TYPE", spec_default=DutyCycleType.CONTINUOUS),
        ] = DutyCycleType.CONTINUOUS

        # Duty cycle fields - conditional on dc_type != CONTINUOUS
        dc_win_open: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Start time of duty cycle-based maneuver window. "
                    "Absolute or relative time tag. Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_WIN_OPEN"),
        ] = None

        dc_win_close: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "End time of duty cycle-based maneuver window. "
                    "Absolute or relative time tag. Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_WIN_CLOSE"),
        ] = None

        dc_min_cycles: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Minimum number of 'ON' duty cycles (may override DC_EXEC_STOP,). "
                    "Optional even when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_MIN_CYCLES"),
        ] = None

        dc_max_cycles: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Maximum number of 'ON' duty cycles (may override DC_EXEC_STOP,). "
                    "Optional even when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_MAX_CYCLES"),
        ] = None

        dc_exec_start: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Start time of initial duty cycle execution sequence. "
                    "Absolute or relative time tag. Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_EXEC_START"),
        ] = None

        dc_exec_stop: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "End time of final duty cycle execution sequence. "
                    "Absolute or relative time tag. Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_EXEC_STOP"),
        ] = None

        dc_ref_time: Annotated[
            CCSDSTimeTag,
            Field(
                default=None,
                description=(
                    "Reference time for the THRUST duty cycle. "
                    "Absolute or relative time tag. Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_REF_TIME"),
        ] = None

        dc_time_pulse_duration: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Thruster pulse 'ON' duration. [s] "
                    "Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(
                keyword="DC_TIME_PULSE_DURATION",
                units="s",
            ),
        ] = None

        dc_time_pulse_period: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Elapsed time between start of one pulse and start of the next. [s] "
                    "Must be >= DC_TIME_PULSE_DURATION. Required when DC_TYPE != CONTINUOUS."
                ),
            ),
            FieldMetadata(
                keyword="DC_TIME_PULSE_PERIOD",
                units="s",
            ),
        ] = None

        # Additional duty cycle fields for TIME_AND_ANGLE mode
        dc_ref_dir: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Reference vector direction in MAN_REF_FRAME (3-element space-delimited "
                    "vector string, per 7.6,). Required when DC_TYPE = TIME_AND_ANGLE."
                ),
            ),
            FieldMetadata(keyword="DC_REF_DIR"),
        ] = None

        dc_body_frame: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Body reference frame in which DC_BODY_TRIGGER is specified. "
                    "Select from annex B, subsection B6. Required when DC_TYPE = TIME_AND_ANGLE."
                ),
            ),
            FieldMetadata(keyword="DC_BODY_FRAME"),
        ] = None

        dc_body_trigger: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Body frame reference vector in DC_BODY_FRAME (3-element space-delimited "
                    "vector string, per 7.6,). Required when DC_TYPE = TIME_AND_ANGLE."
                ),
            ),
            FieldMetadata(keyword="DC_BODY_TRIGGER"),
        ] = None

        dc_pa_start_angle: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Phase angle offset of thruster pulse start relative to DC_BODY_TRIGGER "
                    "crossing of DC_REF_DIR. [deg] Required when DC_TYPE = TIME_AND_ANGLE."
                ),
            ),
            FieldMetadata(
                keyword="DC_PA_START_ANGLE",
                units="deg",
            ),
        ] = None

        dc_pa_stop_angle: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Phase angle of thruster pulse stop relative to DC_BODY_TRIGGER "
                    "crossing of DC_REF_DIR. [deg] Required when DC_TYPE = TIME_AND_ANGLE."
                ),
            ),
            FieldMetadata(
                keyword="DC_PA_STOP_ANGLE",
                units="deg",
            ),
        ] = None

        man_composition: Annotated[
            str,
            Field(
                description=(
                    "Comma-delimited ordered set of maneuver elements on every data line. "
                    "Values drawn from table 6-8 (propulsive) or table 6-9 (deployment). "
                    "Must include exactly one time specification (TIME_ABSOLUTE or TIME_RELATIVE). "
                    "Keywords unique to table 6-8 and table 6-9 shall not be commingled. "
                    "Example: TIME_RELATIVE, THR_X, THR_Y, THR_Z, THR_ISP."
                ),
            ),
            FieldMetadata(keyword="MAN_COMPOSITION"),
        ]

        man_units: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-delimited SI unit designations for each element of the maneuver "
                    "data following the time tag, for informational purposes only. "
                    "Enclosed in square brackets. Does not override mandatory units in table 6-8/6-9."
                ),
            ),
            FieldMetadata(keyword="MAN_UNITS"),
        ] = None

        # Raw maneuver data lines; at least one is required.
        data_lines: Annotated[
            list[ManeuverDataLine | DeploymentDataLine],
            Field(
                min_length=1,
                description=(
                    "Maneuver time history lines as typed rows - ``ManeuverDataLine`` "
                    "(table 6-8, propulsive) or ``DeploymentDataLine`` (table 6-9), one "
                    "value per MAN_COMPOSITION column. At least one is required "
                    "(table 6-7). The KVN/XML adapters parse raw lines into these rows "
                    "and serialize them back."
                ),
            ),
        ]

        @field_validator("man_composition")
        @classmethod
        def validate_man_composition_has_one_time(cls, v: str) -> str:
            elements: list[str] = [e.strip().upper() for e in v.split(",")]
            time_specs: list[str] = [
                e for e in elements if e in ("TIME_ABSOLUTE", "TIME_RELATIVE")
            ]
            if len(time_specs) != 1:
                raise ValueError(
                    "man_composition must contain exactly one time specification "
                    "(TIME_ABSOLUTE or TIME_RELATIVE) per 6.2.8.18."
                )

            # Section 6.2.8.14: at least one element beyond the time tag is required.
            non_time = [
                e for e in elements if e not in {"TIME_ABSOLUTE", "TIME_RELATIVE"}
            ]
            if not non_time:
                raise ValueError(
                    "man_composition must contain at least one element after the time "
                    "specification per 6.2.8.14."
                )

            # Section 6.2.8.15: table 6-8 (propulsive) and 6-9 (deployment) not commingled.
            _ORDER_6_8: list[str] = [
                "TIME_ABSOLUTE",
                "TIME_RELATIVE",
                "MAN_DURA",
                "DELTA_MASS",
                "ACC_X",
                "ACC_Y",
                "ACC_Z",
                "ACC_INTERP",
                "ACC_MAG_SIGMA",
                "ACC_DIR_SIGMA",
                "DV_X",
                "DV_Y",
                "DV_Z",
                "DV_MAG_SIGMA",
                "DV_DIR_SIGMA",
                "THR_X",
                "THR_Y",
                "THR_Z",
                "THR_EFFIC",
                "THR_INTERP",
                "THR_ISP",
                "ISP",
                "THR_MAG_SIGMA",
                "THR_DIR_SIGMA",
            ]
            _ORDER_6_9: list[str] = [
                "TIME_ABSOLUTE",
                "TIME_RELATIVE",
                "DEPLOY_ID",
                "DEPLOY_DV_X",
                "DEPLOY_DV_Y",
                "DEPLOY_DV_Z",
                "DEPLOY_MASS",
                "DEPLOY_DV_SIGMA",
                "DEPLOY_DIR_SIGMA",
                "DEPLOY_DV_RATIO",
                "DEPLOY_DV_CDA",
            ]
            _EXCLUSIVE_6_8: set[str] = set(_ORDER_6_8) - set(_ORDER_6_9)
            _EXCLUSIVE_6_9: set[str] = set(_ORDER_6_9) - set(_ORDER_6_8)
            has_6_8: bool = any(e in _EXCLUSIVE_6_8 for e in elements)
            has_6_9: bool = any(e in _EXCLUSIVE_6_9 for e in elements)
            if has_6_8 and has_6_9:
                raise ValueError(
                    "man_composition must not commingle fields from table 6-8 "
                    "(propulsive) and table 6-9 (deployment) per 6.2.8.15."
                )

            # Section 6.2.8.16: values must appear in the order fixed in table 6-8 or 6-9.
            # Order is verified by checking that the position of each element in
            # the composition does not precede the position of any earlier element.
            # Unknown tokens (not in the applicable table) are rejected per 6.2.8.15.
            order: list[str] = _ORDER_6_9 if has_6_9 else _ORDER_6_8
            pos_map: dict[str, int] = {kw: i for i, kw in enumerate(order)}
            if unknown := [e for e in elements if e not in pos_map]:
                raise ValueError(
                    f"man_composition contains unrecognized tokens {unknown}; all tokens "
                    "must appear in table 6-8 (propulsive) or table 6-9 (deployment) "
                    "per 6.2.8.15."
                )
            if (positions := [pos_map[e] for e in elements]) != sorted(positions):
                raise ValueError(
                    "man_composition elements must appear in the order defined in "
                    "table 6-8 (propulsive) or table 6-9 (deployment) per 6.2.8.16."
                )

            # Section 6.2.8.20: DV components require MAN_DURA.
            _DV: set[str] = {"DV_X", "DV_Y", "DV_Z"}
            if _DV & set(elements) and "MAN_DURA" not in elements:
                raise ValueError(
                    "man_composition includes DV_X/Y/Z but MAN_DURA is absent; "
                    "MAN_DURA is required to locate the impulsive delta-V (6.2.8.20)."
                )

            # Section 6.2.8.20.10 / 6.2.8.21 / 6.2.8.22: 3-vector co-presence.
            for vec in (
                {"ACC_X", "ACC_Y", "ACC_Z"},
                {"DV_X", "DV_Y", "DV_Z"},
                {"THR_X", "THR_Y", "THR_Z"},
            ):
                present = vec & set(elements)
                if present and present != vec:
                    raise ValueError(
                        f"man_composition includes {sorted(present)} but not the full "
                        f"3-vector {sorted(vec)}; all three components must appear together "
                        "(6.2.8.20.10 / 6.2.8.21 / 6.2.8.22)."
                    )

            return v

        @model_validator(mode="after")
        def validate_dc_time_fields_required(self) -> OCM.ManeuverSpecification:
            if self.dc_type in {DutyCycleType.TIME, DutyCycleType.TIME_AND_ANGLE}:
                required: dict[str, str | float | None] = {
                    "dc_win_open": self.dc_win_open,
                    "dc_win_close": self.dc_win_close,
                    "dc_exec_start": self.dc_exec_start,
                    "dc_exec_stop": self.dc_exec_stop,
                    "dc_ref_time": self.dc_ref_time,
                    "dc_time_pulse_duration": self.dc_time_pulse_duration,
                    "dc_time_pulse_period": self.dc_time_pulse_period,
                }
                missing: list[str] = [
                    name for name, val in required.items() if val is None
                ]
                if missing:
                    raise ValueError(
                        f"The following fields are required when dc_type='{self.dc_type}' "
                        f"(6.2.8.20.6): {', '.join(missing)}."
                    )
            return self

        @model_validator(mode="after")
        def validate_dc_angle_fields_required(self) -> OCM.ManeuverSpecification:
            if self.dc_type == DutyCycleType.TIME_AND_ANGLE:
                required: dict[str, str | float | None] = {
                    "dc_ref_dir": self.dc_ref_dir,
                    "dc_body_frame": self.dc_body_frame,
                    "dc_body_trigger": self.dc_body_trigger,
                    "dc_pa_start_angle": self.dc_pa_start_angle,
                    "dc_pa_stop_angle": self.dc_pa_stop_angle,
                }
                missing: list[str] = [
                    name for name, val in required.items() if val is None
                ]
                if missing:
                    raise ValueError(
                        f"The following fields are required when dc_type='TIME_AND_ANGLE' "
                        f"(6.2.8.20.7): {', '.join(missing)}."
                    )
            return self

        @field_validator("dc_ref_dir")
        @classmethod
        def _validate_dc_ref_dir_vector(cls, v: str | None) -> str | None:
            # DC_REF_DIR is a three-element vector (table 6-7, page 6-43) written
            # as space-delimited numeric components (7.6.1). Each token must be a
            # CCSDS numeric literal - the same lexical form as a relative time tag.
            if v is not None:
                tokens: list[str] = v.split()
                if len(tokens) != 3 or not all(
                    _REL_TIME_TAG_RE.fullmatch(t) for t in tokens
                ):
                    raise ValueError(
                        f"dc_ref_dir must be three space-delimited numeric components "
                        f"(table 6-7, 7.6.1), got {v!r}."
                    )
            return v

        @field_validator("dc_body_trigger")
        @classmethod
        def _validate_dc_body_trigger_vector(cls, v: str | None) -> str | None:
            # DC_BODY_TRIGGER is a space-delimited numeric direction vector (7.6.1
            # groups it with DC_REF_DIR as "values containing more than one
            # number"). The spec fixes DC_REF_DIR at three elements but does not
            # state an exact count for DC_BODY_TRIGGER, so only "at least two
            # numeric components" is enforced here.
            if v is not None:
                tokens: list[str] = v.split()
                if len(tokens) < 2 or not all(
                    _REL_TIME_TAG_RE.fullmatch(t) for t in tokens
                ):
                    raise ValueError(
                        f"dc_body_trigger must be space-delimited numeric components "
                        f"(7.6.1), got {v!r}."
                    )
            return v

        @model_validator(mode="after")
        def validate_dc_execution_within_window(self) -> OCM.ManeuverSpecification:
            """
            Duty-cycle execution must fall within the duty-cycle window.

            Table 6-7 (page 6-42) states DC_EXEC_START "must be scheduled to occur
            coincident with or after DC_WIN_OPEN" and DC_EXEC_STOP "coincident with
            or prior to DC_WIN_CLOSE". Time tags may be absolute or relative; this
            block-level check orders same-format pairs, which need no external
            context. Mixed relative/absolute pairs need EPOCH_TZERO (held on
            OCM.Metadata) to reconcile, so they are ordered by
            ``OCM.validate_maneuver_dc_windows_across_formats`` instead.
            """
            if self.dc_exec_start is not None and self.dc_win_open is not None:
                order = _compare_same_format_time_tags(
                    self.dc_exec_start, self.dc_win_open
                )
                if order is not None and order < 0:
                    raise ValueError(
                        "dc_exec_start must be coincident with or after dc_win_open "
                        "(table 6-7, 6.2.8.20.6)."
                    )
            if self.dc_exec_stop is not None and self.dc_win_close is not None:
                order = _compare_same_format_time_tags(
                    self.dc_exec_stop, self.dc_win_close
                )
                if order is not None and order > 0:
                    raise ValueError(
                        "dc_exec_stop must be coincident with or prior to dc_win_close "
                        "(table 6-7, 6.2.8.20.6)."
                    )
            return self

        @field_validator("man_units")
        @classmethod
        def _validate_man_units_brackets(cls, v: str | None) -> str | None:
            if v is not None and not (v.startswith("[") and v.endswith("]")):
                raise ValueError(
                    f"man_units must be enclosed in square brackets "
                    f"(e.g. '[N,N,N]'), got {v!r} (table 6-7)."
                )
            return v

        @model_validator(mode="after")
        def validate_man_units_element_count(self) -> OCM.ManeuverSpecification:
            """
            Cross-check MAN_UNITS element count against MAN_COMPOSITION.

            When MAN_UNITS is present, the spec text (table 6-7, page 91) says one
            unit per element *after* the time tag (=> one fewer than
            MAN_COMPOSITION), but the CCSDS 502.0-B-3 Annex G example on page 206
            (and the second maneuver block of the ocm_g17 fixture) instead prefixes
            an 'n/a' unit for the time tag (=> equal to MAN_COMPOSITION). Both forms
            appear in the normative document, so either count is accepted; only a
            genuine mismatch is rejected. ``man_composition`` is already validated
            (single time spec, known vocabulary) by the time this runs. Per-column
            data-line arity is guaranteed structurally: rows are typed
            ``ManeuverDataLine``/``DeploymentDataLine`` populated column-by-column
            from MAN_COMPOSITION by the KVN/XML readers.
            """
            if self.man_units is None:
                return self
            expected: int = len(
                [e.strip() for e in self.man_composition.split(",") if e.strip()]
            )
            units: list[str] = [
                u.strip() for u in self.man_units.strip("[]").split(",") if u.strip()
            ]
            if len(units) not in {expected - 1, expected}:
                raise ValueError(
                    f"MAN_UNITS lists {len(units)} unit(s) but MAN_COMPOSITION "
                    f"declares {expected} element(s); expected {expected - 1} (one "
                    f"per element after the time tag, table 6-7) or {expected} "
                    f"(with a leading time-tag unit, per the Annex G example). "
                    f"Got {self.man_units!r}."
                )
            return self

        @model_validator(mode="after")
        def validate_rows_match_composition_table(self) -> OCM.ManeuverSpecification:
            """
            Every data-line row must be from the same table as MAN_COMPOSITION.

            MAN_COMPOSITION draws from table 6-8 (propulsive) or table 6-9
            (deployment), never both (enforced by
            ``validate_man_composition_has_one_time``). The rows must match: a
            deployment composition takes ``DeploymentDataLine`` rows, a propulsive
            one takes ``ManeuverDataLine`` rows (6.2.8.15).
            """
            is_deployment: bool = any(
                e.strip().upper().startswith("DEPLOY")
                for e in self.man_composition.split(",")
            )
            expected_type: type = (
                OCM.ManeuverSpecification.DeploymentDataLine
                if is_deployment
                else OCM.ManeuverSpecification.ManeuverDataLine
            )
            for index, row in enumerate(self.data_lines):
                if not isinstance(row, expected_type):
                    # ValueError (not TypeError) so Pydantic surfaces it as a
                    # ValidationError; this is a spec-consistency violation, not a
                    # Python type error.
                    raise ValueError(  # noqa: TRY004
                        f"Maneuver data-line row {index} is a "
                        f"{type(row).__name__}, but MAN_COMPOSITION is "
                        f"{'deployment' if is_deployment else 'propulsive'} "
                        f"(expects {expected_type.__name__}) (6.2.8.15)."
                    )
            return self

        @model_validator(mode="after")
        def _validate_dc_cycles_order(self) -> OCM.ManeuverSpecification:
            if (
                self.dc_min_cycles is not None
                and self.dc_max_cycles is not None
                and self.dc_min_cycles > self.dc_max_cycles
            ):
                raise ValueError(
                    f"dc_min_cycles ({self.dc_min_cycles}) must be <= "
                    f"dc_max_cycles ({self.dc_max_cycles}) (table 6-7)."
                )
            return self

        @model_validator(mode="after")
        def validate_pulse_period_ge_duration(self) -> OCM.ManeuverSpecification:
            if (
                self.dc_time_pulse_duration is not None
                and self.dc_time_pulse_period is not None
                and self.dc_time_pulse_period < self.dc_time_pulse_duration
            ):
                raise ValueError(
                    "dc_time_pulse_period must be greater than or equal to "
                    "dc_time_pulse_duration (table 6-7)."
                )
            return self

        @model_validator(mode="after")
        def validate_no_duplicate_time_tags(self) -> OCM.ManeuverSpecification:
            """
            Reject duplicate time tags in maneuver data (section 6.2.2.4).

            Section 6.2.8 imposes no ordering requirement on maneuver lines; only
            section 6.2.2.4's no-duplicate rule applies here.
            """
            _check_no_duplicate_time_tags(
                [row.time_tag for row in self.data_lines], "maneuver"
            )
            return self

    # -----------------------------------------------------------------------
    # Perturbations Specification (table 6-10)
    # -----------------------------------------------------------------------

    class PerturbationsSpecification(BaseModel):
        """
        Perturbations specification, delimited by PERT_START / PERT_STOP.

        At most one section shall appear in an OCM (6.2.9.2).
        Required when an orbit determination section is included (6.2.10.5).
        Recommended when a trajectory state or covariance section is included
        (6.2.5.14, 6.2.7.11a).

        All fields are optional (table 6-10).
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("PERT_START", "PERT_STOP")
        _xml_tag: ClassVar[str] = "pert"

        comment: Comment = None

        atmospheric_model: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name of atmosphere model. Select from annex B, subsection B9 "
                    "(https://sanaregistry.org/r/atmosphere_models,). "
                    "Examples: MSISE90, NRLMSIS00, J70, J71, JB2008, DTM."
                ),
            ),
            FieldMetadata(keyword="ATMOSPHERIC_MODEL"),
        ] = None

        gravity_model: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Gravity model name (from annex B, subsection B10,) followed by degree (D) "
                    "and order (O) of applied spherical harmonics. "
                    "Examples: 'EGM-96: 36D 36O', 'WGS-84: 8D 0O'. "
                    "Zero order (e.g., '2D 0O') denotes zonals."
                ),
            ),
            FieldMetadata(keyword="GRAVITY_MODEL"),
        ] = None

        equatorial_radius: Annotated[
            float | None,
            Field(
                default=None,
                gt=0,
                description=(
                    "Oblate spheroid equatorial radius of the central body, if different "
                    "from the gravity model. [km]"
                ),
            ),
            FieldMetadata(
                keyword="EQUATORIAL_RADIUS",
                units="km",
            ),
        ] = None

        gm: Annotated[
            float | None,
            Field(
                default=None,
                gt=0,
                description=(
                    "Gravitational coefficient (G x central mass,) of attracting body, "
                    "if different from the gravity model. [km**3/s**2]"
                ),
            ),
            FieldMetadata(
                keyword="GM",
                units="km**3/s**2",
            ),
        ] = None

        n_body_perturbations: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "One or more N-body gravitational perturbation bodies, "
                    "comma-delimited. Values from annex B, subsection B2 (CENTER_NAME,). "
                    "Example: MOON, SUN, JUPITER."
                ),
            ),
            FieldMetadata(keyword="N_BODY_PERTURBATIONS"),
        ] = None

        central_body_rotation: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Central body angular rotation rate about its major principal inertia axis. "
                    "[deg/s]"
                ),
            ),
            FieldMetadata(
                keyword="CENTRAL_BODY_ROTATION",
                units="deg/s",
            ),
        ] = None

        oblate_flattening: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Central body's oblate spheroid oblateness. "
                    "For Earth approximately 1/298.257223563 = 0.00335281066475."
                ),
            ),
            FieldMetadata(keyword="OBLATE_FLATTENING"),
        ] = None

        ocean_tides_model: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name of ocean tides model, optionally specifying order/constituent effects "
                    "(e.g. DIURNAL, SEMI-DIURNAL,). Free-text field."
                ),
            ),
            FieldMetadata(keyword="OCEAN_TIDES_MODEL"),
        ] = None

        solid_tides_model: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name of solid tides model, optionally specifying order/constituent effects. "
                    "Free-text field."
                ),
            ),
            FieldMetadata(keyword="SOLID_TIDES_MODEL"),
        ] = None

        reduction_theory: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Specification of the reduction theory for precession/nutation modeling. "
                    "Free-text field. Examples: IAU1976/FK5, IAU2010, IERS1996."
                ),
            ),
            FieldMetadata(keyword="REDUCTION_THEORY"),
        ] = None

        albedo_model: Annotated[
            str | None,
            Field(
                default=None,
                description="Name of the albedo model. Examples: STK.",
            ),
            FieldMetadata(keyword="ALBEDO_MODEL"),
        ] = None

        albedo_grid_size: Annotated[
            int | None,
            Field(
                default=None,
                ge=1,
                description="Number of grid points used in the albedo model.",
            ),
            FieldMetadata(keyword="ALBEDO_GRID_SIZE"),
        ] = None

        shadow_model: Annotated[
            ShadowModel | None,
            Field(
                default=None,
                description=(
                    "Shadow model for Solar Radiation Pressure. "
                    "One of: NONE, CYLINDRICAL, CONE, DUAL_CONE (section 6.2.9, table 6-10,)."
                ),
            ),
            FieldMetadata(keyword="SHADOW_MODEL"),
        ] = None

        shadow_bodies: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-separated list of planetary bodies for which SRP shadowing is modeled. "
                    "Selected from annex B CENTER_NAME values. Example: EARTH, MOON."
                ),
            ),
            FieldMetadata(keyword="SHADOW_BODIES"),
        ] = None

        srp_model: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name of SRP model. Free-text field. "
                    "Examples: GPS_ROCK, BOX_WING, CANNONBALL, COD."
                ),
            ),
            FieldMetadata(keyword="SRP_MODEL"),
        ] = None

        sw_data_source: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Source and version of Space Weather data used. "
                    "Multiple sources may be comma-delimited. Example: CELESTRAK."
                ),
            ),
            FieldMetadata(keyword="SW_DATA_SOURCE"),
        ] = None

        sw_data_epoch: Annotated[
            OptionalCCSDSDate,
            Field(
                default=None,
                description=(
                    "Epoch of the Space Weather data. See 7.5.10 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="SW_DATA_EPOCH"),
        ] = None

        sw_interp_method: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Method to select or interpolate sequential space weather data "
                    "(Kp, ap, Dst, F10.7, etc.,). Free-text field. "
                    "Examples: PRECEDING_VALUE, NEAREST_NEIGHBOR, LINEAR, LAGRANGE_ORDER_5."
                ),
            ),
            FieldMetadata(keyword="SW_INTERP_METHOD"),
        ] = None

        fixed_geomag_kp: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) planetary geomagnetic index Kp. [nT] "
                    "Overrides normal time-varying Kp from SW_DATA_SOURCE."
                ),
            ),
            FieldMetadata(
                keyword="FIXED_GEOMAG_KP",
                units="nT",
            ),
        ] = None

        fixed_geomag_ap: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) geomagnetic index ap. [nT] "
                    "Overrides normal time-varying ap from SW_DATA_SOURCE."
                ),
            ),
            FieldMetadata(
                keyword="FIXED_GEOMAG_AP",
                units="nT",
            ),
        ] = None

        fixed_geomag_dst: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) planetary geomagnetic index Dst. [nT] "
                    "Overrides normal time-varying Dst from SW_DATA_SOURCE."
                ),
            ),
            FieldMetadata(
                keyword="FIXED_GEOMAG_DST",
                units="nT",
            ),
        ] = None

        fixed_f10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) daily solar flux proxy F10.7. [SFU] "
                    "Overrides normal time-varying F10.7."
                ),
            ),
            FieldMetadata(
                keyword="FIXED_F10P7",
                units="SFU",
            ),
        ] = None

        fixed_f10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) averaged solar flux proxy F10.7. [SFU] "
                    "Overrides normal time-varying averaged F10.7."
                ),
            ),
            FieldMetadata(
                keyword="FIXED_F10P7_MEAN",
                units="SFU",
            ),
        ] = None

        fixed_m10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) daily solar flux proxy M10.7. [SFU]"
                ),
            ),
            FieldMetadata(
                keyword="FIXED_M10P7",
                units="SFU",
            ),
        ] = None

        fixed_m10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) averaged solar flux proxy M10.7. [SFU]"
                ),
            ),
            FieldMetadata(
                keyword="FIXED_M10P7_MEAN",
                units="SFU",
            ),
        ] = None

        fixed_s10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) daily solar flux proxy S10.7. [SFU]"
                ),
            ),
            FieldMetadata(
                keyword="FIXED_S10P7",
                units="SFU",
            ),
        ] = None

        fixed_s10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) averaged solar flux proxy S10.7. [SFU]"
                ),
            ),
            FieldMetadata(
                keyword="FIXED_S10P7_MEAN",
                units="SFU",
            ),
        ] = None

        fixed_y10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) daily solar flux proxy Y10.7. [SFU]"
                ),
            ),
            FieldMetadata(
                keyword="FIXED_Y10P7",
                units="SFU",
            ),
        ] = None

        fixed_y10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant,) averaged solar flux proxy Y10.7. [SFU]"
                ),
            ),
            FieldMetadata(
                keyword="FIXED_Y10P7_MEAN",
                units="SFU",
            ),
        ] = None

        # table 6-10: GRAVITY_MODEL compound format "<name>: <N>D <N>O"
        @field_validator("gravity_model")
        @classmethod
        def _validate_gravity_model_format(cls, v: str | None) -> str | None:
            if v is not None and not re.match(r"^.+: \d+D \d+O$", v):
                raise ValueError(
                    "GRAVITY_MODEL must have format '<name>: <N>D <N>O' "
                    f"(e.g., 'EGM-96: 36D 36O'), got: {v!r}"
                )
            return v

    # -----------------------------------------------------------------------
    # Orbit Determination Data (table 6-11)
    # -----------------------------------------------------------------------

    class OrbitDeterminationData(BaseModel):
        """
        Orbit determination data, delimited by OD_START / OD_STOP.

        At most one section shall appear in an OCM (6.2.10.2).
        OD_ID, OD_METHOD, and OD_EPOCH are mandatory (table 6-11).
        All other fields are optional.

        When an OD section is included, a perturbations section shall also be
        included (6.2.10.5); this cross-block rule is enforced in the top-level
        OCM model_validator.
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("OD_START", "OD_STOP")
        _xml_tag: ClassVar[str] = "od"

        comment: Comment = None

        od_id: Annotated[
            str,
            Field(
                description=(
                    "Identification number for this orbit determination. "
                    "Should match TRAJ_BASIS_ID, COV_BASIS_ID, and/or MAN_BASIS_ID "
                    "when those blocks reference this OD (6.2.10.6,)."
                ),
            ),
            FieldMetadata(keyword="OD_ID"),
        ]

        od_prev_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Identification number for the previous orbit determination. "
                    "Omit if this is the first."
                ),
            ),
            FieldMetadata(keyword="OD_PREV_ID"),
        ] = None

        od_method: Annotated[
            str,
            Field(
                description=(
                    "Type of orbit determination method used. Free-text; suggested format: "
                    "'<method>: <tool>', e.g. 'BWLS: ODIN', 'EKF: ODTK', 'SF: ODTK'. "
                    "Common methods: BWLS (Batch Weighted Least Squares,), EKF (Extended Kalman "
                    "Filter), SF (Sequential Filter), SRIF, SSEM."
                ),
            ),
            FieldMetadata(keyword="OD_METHOD"),
        ]

        od_epoch: Annotated[
            TimeTag,
            Field(
                description=(
                    "Relative or absolute time tag of the OD solved-for state in the OCM "
                    "time system. See 7.5.10."
                ),
            ),
            FieldMetadata(keyword="OD_EPOCH"),
        ]

        days_since_first_obs: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Days elapsed between first accepted observation and OD_EPOCH. [d] "
                    "May be positive or negative (relative to OD_EPOCH, per 6.2.10.4,)."
                ),
            ),
            FieldMetadata(
                keyword="DAYS_SINCE_FIRST_OBS",
                units="d",
            ),
        ] = None

        days_since_last_obs: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Days elapsed between last accepted observation and OD_EPOCH. [d] "
                    "May be positive or negative (relative to OD_EPOCH, per 6.2.10.4,)."
                ),
            ),
            FieldMetadata(
                keyword="DAYS_SINCE_LAST_OBS",
                units="d",
            ),
        ] = None

        recommended_od_span: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description=(
                    "Number of days of observations recommended for OD of the object. [d] "
                    "Useful only for Batch OD systems."
                ),
            ),
            FieldMetadata(
                keyword="RECOMMENDED_OD_SPAN",
                units="d",
            ),
        ] = None

        actual_od_span: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description=(
                    "Actual time span in days used for the OD. [d] "
                    "Should equal DAYS_SINCE_FIRST_OBS - DAYS_SINCE_LAST_OBS."
                ),
            ),
            FieldMetadata(
                keyword="ACTUAL_OD_SPAN",
                units="d",
            ),
        ] = None

        obs_available: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of observations available within the actual OD time span.",
            ),
            FieldMetadata(keyword="OBS_AVAILABLE"),
        ] = None

        obs_used: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of observations accepted within the actual OD time span.",
            ),
            FieldMetadata(keyword="OBS_USED"),
        ] = None

        tracks_available: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of sensor tracks available for OD within the actual time span.",
            ),
            FieldMetadata(keyword="TRACKS_AVAILABLE"),
        ] = None

        tracks_used: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of sensor tracks accepted for OD within the actual time span.",
            ),
            FieldMetadata(keyword="TRACKS_USED"),
        ] = None

        maximum_obs_gap: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description="Maximum time between observations in the OD. [d]",
            ),
            FieldMetadata(
                keyword="MAXIMUM_OBS_GAP",
                units="d",
            ),
        ] = None

        od_epoch_eigmaj: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description="Positional error ellipsoid 1-sigma major eigenvalue at OD epoch. [m]",
            ),
            FieldMetadata(
                keyword="OD_EPOCH_EIGMAJ",
                units="m",
            ),
        ] = None

        od_epoch_eigint: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description="Positional error ellipsoid 1-sigma intermediate eigenvalue at OD epoch. [m]",
            ),
            FieldMetadata(
                keyword="OD_EPOCH_EIGINT",
                units="m",
            ),
        ] = None

        od_epoch_eigmin: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description="Positional error ellipsoid 1-sigma minor eigenvalue at OD epoch. [m]",
            ),
            FieldMetadata(
                keyword="OD_EPOCH_EIGMIN",
                units="m",
            ),
        ] = None

        od_max_pred_eigmaj: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description=(
                    "Maximum predicted major eigenvalue of the 1-sigma positional error ellipsoid "
                    "over the entire TIME_SPAN of the OCM. [m]"
                ),
            ),
            FieldMetadata(
                keyword="OD_MAX_PRED_EIGMAJ",
                units="m",
            ),
        ] = None

        od_min_pred_eigmin: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description=(
                    "Minimum predicted minor eigenvalue of the 1-sigma positional error ellipsoid "
                    "over the entire TIME_SPAN of the OCM. [m]"
                ),
            ),
            FieldMetadata(
                keyword="OD_MIN_PRED_EIGMIN",
                units="m",
            ),
        ] = None

        od_confidence: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                le=100,
                description=(
                    "OD confidence metric spanning 0 to 100%. [%] "
                    "Useful only for Filter-based OD systems. "
                    "Defined by mutual agreement of message exchange participants."
                ),
            ),
            FieldMetadata(
                keyword="OD_CONFIDENCE",
                units="%",
            ),
        ] = None

        gdop: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description=(
                    "Generalized Dilution Of Precision for this OD, based on the "
                    "observability grammian (annex F, subsection F4,). Ideal value approximately 1.0."
                ),
            ),
            FieldMetadata(keyword="GDOP"),
        ] = None

        solve_n: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of solve-for states in the orbit determination.",
            ),
            FieldMetadata(keyword="SOLVE_N"),
        ] = None

        solve_states: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Free-text comma-delimited description of the solved-for state elements. "
                    "Example: POS[3], VEL[3]."
                ),
            ),
            FieldMetadata(keyword="SOLVE_STATES"),
        ] = None

        consider_n: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of consider parameters used in the orbit determination.",
            ),
            FieldMetadata(keyword="CONSIDER_N"),
        ] = None

        consider_params: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Free-text comma-delimited description of the consider parameters. "
                    "Example: DRAG, SRP."
                ),
            ),
            FieldMetadata(keyword="CONSIDER_PARAMS"),
        ] = None

        sedr: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Specific Energy Dissipation Rate: energy removed from orbit by "
                    "non-conservative forces, averaged during OD. [W/kg] "
                    "(See annex F, subsection F7.,)"
                ),
            ),
            FieldMetadata(
                keyword="SEDR",
                units="W/kg",
            ),
        ] = None

        sensors_n: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Number of sensors used in the orbit determination.",
            ),
            FieldMetadata(keyword="SENSORS_N"),
        ] = None

        sensors: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Free-text comma-delimited description of the sensors used in OD. "
                    "Example: EGLIN, FYLINGDALES."
                ),
            ),
            FieldMetadata(keyword="SENSORS"),
        ] = None

        weighted_rms: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                description=(
                    "Weighted RMS residual ratio (useful only for Batch OD systems,). "
                    "A value of 1.0 is ideal. See table 6-11 for definition."
                ),
            ),
            FieldMetadata(keyword="WEIGHTED_RMS"),
        ] = None

        data_types: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-separated list of observation data types used in OD. "
                    "Free-text; recommended to use TDM table 3-5 descriptors. "
                    "Examples: ANGLE_1, ANGLE_2, RADEC, AZEL, RANGE."
                ),
            ),
            FieldMetadata(keyword="DATA_TYPES"),
        ] = None

        # 6.2.10.4: both fields are (OD_EPOCH - obs_time); since first_obs <= last_obs,
        # DAYS_SINCE_FIRST_OBS >= DAYS_SINCE_LAST_OBS must always hold.
        @model_validator(mode="after")
        def _validate_obs_day_ordering(self) -> OCM.OrbitDeterminationData:
            if (
                self.days_since_first_obs is not None
                and self.days_since_last_obs is not None
                and self.days_since_first_obs < self.days_since_last_obs
            ):
                raise ValueError(
                    "DAYS_SINCE_FIRST_OBS must be >= DAYS_SINCE_LAST_OBS "
                    "(both are relative to OD_EPOCH; the first observation precedes "
                    f"the last, so its offset must be larger: "
                    f"{self.days_since_first_obs} < {self.days_since_last_obs})."
                )
            return self

        @model_validator(mode="after")
        def _validate_obs_used_le_available(self) -> OCM.OrbitDeterminationData:
            if (
                self.obs_used is not None
                and self.obs_available is not None
                and self.obs_used > self.obs_available
            ):
                raise ValueError(
                    f"obs_used ({self.obs_used}) cannot exceed obs_available ({self.obs_available}) (table 6-11)."
                )
            return self

        @model_validator(mode="after")
        def _validate_tracks_used_le_available(self) -> OCM.OrbitDeterminationData:
            if (
                self.tracks_used is not None
                and self.tracks_available is not None
                and self.tracks_used > self.tracks_available
            ):
                raise ValueError(
                    f"tracks_used ({self.tracks_used}) cannot exceed tracks_available ({self.tracks_available}) (table 6-11)."
                )
            return self

        @model_validator(mode="after")
        def _validate_eigenvalue_ordering(self) -> OCM.OrbitDeterminationData:
            eigmaj, eigint, eigmin = (
                self.od_epoch_eigmaj,
                self.od_epoch_eigint,
                self.od_epoch_eigmin,
            )
            # Checking each individually (rather than indexing a shared tuple) narrows
            # each to float for mypy, instead of leaving it as float | None.
            if (
                eigmaj is not None
                and eigint is not None
                and eigmin is not None
                and not (eigmaj >= eigint >= eigmin)
            ):
                raise ValueError(
                    f"Eigenvalues must satisfy OD_EPOCH_EIGMAJ >= OD_EPOCH_EIGINT >= OD_EPOCH_EIGMIN "
                    f"(got {eigmaj} / {eigint} / {eigmin}, table 6-11)."
                )
            return self

    # -----------------------------------------------------------------------
    # User-Defined Parameters (table 6-12)
    # -----------------------------------------------------------------------

    class UserDefinedParameters(BaseModel):
        """
        User-defined parameters, delimited by USER_START / USER_STOP.

        At most one section shall appear in an OCM (6.2.11.2).
        All keywords and their meanings must be described in an ICD (6.2.11.1).
        At least one user-defined entry is required if this block is present.
        """

        model_config = CCSDS_MODEL_CONFIG

        _delineation: ClassVar[Delineation] = Delineation("USER_START", "USER_STOP")
        _xml_tag: ClassVar[str] = "user"

        comment: Comment = None

        user_defined: dict[str, str] = Field(
            default_factory=dict,
            description=(
                "User-defined parameters keyed by the suffix of USER_DEFINED_x. "
                "All parameters must be described in an ICD (6.2.11.1,). "
                "At least one entry is required when this block is present."
            ),
        )

        @model_validator(mode="after")
        def validate_user_defined_not_empty(self) -> OCM.UserDefinedParameters:
            if not self.user_defined:
                raise ValueError(
                    "UserDefinedParameters block must contain at least one entry. "
                    "Omit the block entirely if no user-defined parameters are needed."
                )
            return self

    # -----------------------------------------------------------------------
    # Top-level OCM fields
    # -----------------------------------------------------------------------

    header: Header
    metadata: Metadata

    trajectory_states: list[TrajectoryStateTimeHistory] | None = Field(
        default=None,
        min_length=1,
        description=(
            "One or more trajectory state time history blocks (optional, repeatable,). "
            "Each block is delimited by TRAJ_START / TRAJ_STOP. "
            "A corresponding perturbations section should be included (6.2.5.14)."
        ),
    )

    physical_characteristics: SpaceObjectPhysicalCharacteristics | None = Field(
        default=None,
        description=(
            "Space object physical characteristics block (optional, at most one,). "
            "Delimited by PHYS_START / PHYS_STOP."
        ),
    )

    covariances: list[CovarianceTimeHistory] | None = Field(
        default=None,
        min_length=1,
        description=(
            "One or more covariance time history blocks (optional, repeatable,). "
            "Each block is delimited by COV_START / COV_STOP. "
            "A corresponding perturbations section should be included (6.2.7.11a)."
        ),
    )

    maneuvers: list[ManeuverSpecification] | None = Field(
        default=None,
        min_length=1,
        description=(
            "One or more maneuver specification blocks (optional, repeatable,). "
            "Each block is delimited by MAN_START / MAN_STOP."
        ),
    )

    perturbations: PerturbationsSpecification | None = Field(
        default=None,
        description=(
            "Perturbations specification block (conditional: required when an orbit "
            "determination section is included; recommended when trajectory state or "
            "covariance blocks are present,). Delimited by PERT_START / PERT_STOP. "
            "At most one section shall appear in an OCM (6.2.9.2)."
        ),
    )

    orbit_determination: OrbitDeterminationData | None = Field(
        default=None,
        description=(
            "Orbit determination data block (optional, at most one,). "
            "Delimited by OD_START / OD_STOP. "
            "When present, a perturbations section shall also be present (6.2.10.5)."
        ),
    )

    user_defined: UserDefinedParameters | None = Field(
        default=None,
        description=(
            "User-defined parameters block (optional, at most one,). "
            "Delimited by USER_START / USER_STOP. "
            "All keywords must be described in an ICD."
        ),
    )

    # -----------------------------------------------------------------------
    # Top-level cross-block validators
    # -----------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_perturbations_required_for_od(self) -> OCM:
        """
        Validates that orbit determination requires a perturbations section (6.2.10.5).
        """
        if self.orbit_determination is not None and self.perturbations is None:
            raise ValueError(
                "A perturbations block (perturbations) is required when an orbit "
                "determination block (orbit_determination) is present (6.2.10.5)."
            )
        return self

    @model_validator(mode="after")
    def validate_maneuver_dc_windows_across_formats(self) -> OCM:
        """
        Order DC execution vs window tags that mix relative and absolute formats.

        ``ManeuverSpecification.validate_dc_execution_within_window`` orders
        same-format pairs; when one tag is relative (seconds) and the other
        absolute, it abstains because the comparison needs ``EPOCH_TZERO``. Here at
        the OCM level that value is available, so mixed pairs are resolved to
        absolute instants and ordered per table 6-7: DC_EXEC_START coincident with
        or after DC_WIN_OPEN, DC_EXEC_STOP coincident with or prior to DC_WIN_CLOSE.
        """
        tzero: str = self.metadata.epoch_tzero
        for index, man in enumerate(self.maneuvers or []):
            if (
                man.dc_exec_start is not None
                and man.dc_win_open is not None
                and _compare_same_format_time_tags(man.dc_exec_start, man.dc_win_open)
                is None
                and _resolve_time_tag(man.dc_exec_start, tzero)
                < _resolve_time_tag(man.dc_win_open, tzero)
            ):
                raise ValueError(
                    f"Maneuver block {index}: dc_exec_start must be coincident with or "
                    f"after dc_win_open (table 6-7, 6.2.8.20.6)."
                )
            if (
                man.dc_exec_stop is not None
                and man.dc_win_close is not None
                and _compare_same_format_time_tags(man.dc_exec_stop, man.dc_win_close)
                is None
                and _resolve_time_tag(man.dc_exec_stop, tzero)
                > _resolve_time_tag(man.dc_win_close, tzero)
            ):
                raise ValueError(
                    f"Maneuver block {index}: dc_exec_stop must be coincident with or "
                    f"prior to dc_win_close (table 6-7, 6.2.8.20.6)."
                )
        return self

    @classmethod
    def builder(cls) -> OCMBuilder:
        """
        Return a fluent builder for constructing this message type.

        Use `model_copy(update={...})` to create modified copies of a frozen instance.
        """
        return OCMBuilder()

    def composite_maneuver_groups(self) -> list[list[OCM.ManeuverSpecification]]:
        """
        Group maneuver blocks that constitute one composite maneuver (section 6.2.8.11).

        Per section 6.2.8.11, maneuver constituents sharing the same MAN_ID, MAN_BASIS, and
        MAN_REF_FRAME "shall be added together to obtain the total composite maneuver
        description". This returns those constituent groups, preserving first-seen
        order both within and across groups.

        The physical summation of a group is intentionally left to the caller: the
        spec defines no canonical element-wise combination across constituents with
        differing MAN_COMPOSITION or time grids, so it is a modeling choice rather
        than a message-level operation. Inspect ``group[0].man_id`` etc. to identify
        each group.

        Returns:
            list[list[OCM.ManeuverSpecification]]: One inner list per composite
            maneuver; empty when the message has no maneuver blocks.
        """
        CompositeKey = tuple[
            str, ManeuverBasis | None, RefFrame | ExtendedManCovRefFrame | str
        ]
        groups: dict[CompositeKey, list[OCM.ManeuverSpecification]] = {}
        for maneuver in self.maneuvers or []:
            key: CompositeKey = (
                maneuver.man_id,
                maneuver.man_basis,
                maneuver.man_ref_frame,
            )
            groups.setdefault(key, []).append(maneuver)
        return list(groups.values())


class OCMBuilder:
    """
    Fluent builder for :class:`OCM`.

    Call methods in any order, then call :meth:`build` to validate and
    return a frozen :class:`OCM` instance.
    """

    def __init__(self) -> None:
        self._header_kwargs: dict[str, Any] = {}
        self._metadata_kwargs: dict[str, Any] = {}
        self._trajectory_states: list[OCM.TrajectoryStateTimeHistory] = []
        self._physical_characteristics_kwargs: dict[str, Any] | None = None
        self._covariances: list[OCM.CovarianceTimeHistory] = []
        self._maneuvers: list[OCM.ManeuverSpecification] = []
        self._perturbations_kwargs: dict[str, Any] | None = None
        self._orbit_determination_kwargs: dict[str, Any] | None = None
        self._user_defined_kwargs: dict[str, str] | None = None

    def header(
        self,
        *,
        originator: str,
        creation_date: str | None = None,
        message_id: str | None = None,
        comment: list[str] | None = None,
    ) -> OCMBuilder:
        """
        Set header fields.

        Args:
            originator: Originator of the message.
            creation_date: CCSDS creation date string; defaults to the current UTC time.
            message_id: Optional message identifier.
            comment: Optional list of comment strings.
        """
        self._header_kwargs = {
            "ccsds_ocm_vers": "3.0",
            "originator": originator,
            **({"creation_date": creation_date} if creation_date is not None else {}),
        }
        if message_id is not None:
            self._header_kwargs["message_id"] = message_id
        if comment is not None:
            self._header_kwargs["comment"] = comment
        return self

    def metadata(self, **kwargs: Any) -> OCMBuilder:
        """
        Set metadata fields.

        Pass keyword arguments matching :class:`OCM.Metadata` fields.
        `time_system` and `epoch_tzero` are mandatory.
        """
        self._metadata_kwargs = kwargs
        return self

    def add_trajectory(
        self,
        *,
        data_lines: list[str],
        **kwargs: Any,
    ) -> OCMBuilder:
        """
        Append one trajectory state time history block.

        Args:
            data_lines: Non-empty list of raw trajectory state lines, each
                beginning with an absolute or relative time tag.
            **kwargs: Additional keyword arguments for
                :class:`OCM.TrajectoryStateTimeHistory` (e.g. `traj_type`,
                `traj_ref_frame`, `center_name`).
        """
        self._trajectory_states.append(
            OCM.TrajectoryStateTimeHistory(data_lines=data_lines, **kwargs)
        )
        return self

    def physical_characteristics(self, **kwargs: Any) -> OCMBuilder:
        """
        Set optional space object physical characteristics.

        Pass keyword arguments matching :class:`OCM.SpaceObjectPhysicalCharacteristics`
        fields. All fields are optional.
        """
        self._physical_characteristics_kwargs = kwargs
        return self

    def add_covariance(
        self,
        *,
        data_lines: list[str],
        **kwargs: Any,
    ) -> OCMBuilder:
        """
        Append one covariance time history block.

        Args:
            data_lines: Non-empty list of raw covariance data lines.
            **kwargs: Additional keyword arguments for
                :class:`OCM.CovarianceTimeHistory` (e.g. `cov_ref_frame`,
                `cov_type`, `cov_ordering`).
        """
        self._covariances.append(
            OCM.CovarianceTimeHistory(data_lines=data_lines, **kwargs)
        )
        return self

    def add_maneuver(
        self,
        *,
        data_lines: list[str],
        **kwargs: Any,
    ) -> OCMBuilder:
        """
        Append one maneuver specification block.

        Args:
            data_lines: Non-empty list of raw maneuver data lines.
            **kwargs: Additional keyword arguments for
                :class:`OCM.ManeuverSpecification` (e.g. `man_id`,
                `man_device_id`, `man_ref_frame`, `dc_type`,
                `man_composition`).
        """
        self._maneuvers.append(OCM.ManeuverSpecification(data_lines=data_lines, **kwargs))
        return self

    def perturbations(self, **kwargs: Any) -> OCMBuilder:
        """
        Set optional perturbations specification.

        Pass keyword arguments matching :class:`OCM.PerturbationsSpecification`
        fields. All fields are optional. Required when an orbit determination
        block is included.
        """
        self._perturbations_kwargs = kwargs
        return self

    def orbit_determination(self, **kwargs: Any) -> OCMBuilder:
        """
        Set optional orbit determination data.

        Pass keyword arguments matching :class:`OCM.OrbitDeterminationData`
        fields. `od_id`, `od_method`, and `od_epoch` are mandatory.
        A perturbations block must also be set when this is used.
        """
        self._orbit_determination_kwargs = kwargs
        return self

    def user_defined(self, **kwargs: str) -> OCMBuilder:
        """
        Set optional user-defined parameters.

        Pass keyword arguments whose values are strings; each becomes a
        `USER_DEFINED_<key>` entry. All parameters must be described in an ICD.
        """
        self._user_defined_kwargs = dict(kwargs)
        return self

    def build(self) -> OCM:
        """
        Validate and return a frozen :class:`OCM` instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        header_kw: dict[str, Any] = dict(self._header_kwargs)
        if "creation_date" not in header_kw:
            header_kw["creation_date"] = (
                datetime.now(UTC).strftime("%Y-%jT%H:%M:%S.%f")[:-3] + "Z"
            )
        physical_characteristics: OCM.SpaceObjectPhysicalCharacteristics | None = (
            OCM.SpaceObjectPhysicalCharacteristics(
                **self._physical_characteristics_kwargs
            )
            if self._physical_characteristics_kwargs is not None
            else None
        )
        perturbations: OCM.PerturbationsSpecification | None = (
            OCM.PerturbationsSpecification(**self._perturbations_kwargs)
            if self._perturbations_kwargs is not None
            else None
        )
        orbit_determination: OCM.OrbitDeterminationData | None = (
            OCM.OrbitDeterminationData(**self._orbit_determination_kwargs)
            if self._orbit_determination_kwargs is not None
            else None
        )
        user_defined_parameters: OCM.UserDefinedParameters | None = (
            OCM.UserDefinedParameters(user_defined=self._user_defined_kwargs)
            if self._user_defined_kwargs is not None
            else None
        )

        return OCM(
            header=OCM.Header(**header_kw),
            metadata=OCM.Metadata(**self._metadata_kwargs),
            trajectory_states=(self._trajectory_states or None),
            physical_characteristics=physical_characteristics,
            covariances=self._covariances or None,
            maneuvers=self._maneuvers or None,
            perturbations=perturbations,
            orbit_determination=orbit_determination,
            user_defined=user_defined_parameters,
        )
