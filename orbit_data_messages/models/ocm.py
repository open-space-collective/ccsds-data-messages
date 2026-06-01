from __future__ import annotations

import re
from typing import Annotated
from typing import ClassVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import FieldValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from .base import CCSDSDataMessage
from ._epoch import _epoch_sort_key
from ._epoch import _RELATIVE_TIME_RE
from ._epoch import _validate_ccsds_date
from ._epoch import _validate_time_tag
from .metadata import Delineation
from .metadata import FieldMetadata
from .values import CenterName
from .values import CovarianceOrdering
from .values import CovarianceType
from .values import DutyCycleType
from .values import Interpolation
from .values import ManCovRefFrame
from .values import ManeuverBasis
from .values import ObjectType
from .values import OperationalStatus
from .values import OrbitalElements
from .values import RefFrame
from .values import ShadowModel
from .values import TimeSystem


def _check_data_lines_ordered(data_lines: list[str], block_name: str) -> None:
    """Assert that data_lines are strictly increasing by time tag.

    Detects relative vs absolute tags from the first line and compares
    accordingly (§6.2.2.5 forbids mixing within a block). Strict ordering
    also enforces the no-duplicate rule of §6.2.2.4.

    Args:
        data_lines (list[str]): Raw data lines to validate.
        block_name (str): Section name used in error messages (e.g. ``"trajectory state"``).

    Raises:
        ValueError: If any time tag is not strictly greater than the preceding one.
    """
    if len(data_lines) < 2:
        return
    tags: list[str] = [line.split()[0] for line in data_lines]
    if _RELATIVE_TIME_RE.fullmatch(tags[0]):
        keys: list[float] = [float(t) for t in tags]
        for i in range(1, len(keys)):
            if keys[i] <= keys[i - 1]:
                raise ValueError(
                    f"{block_name} data_lines must be strictly increasing "
                    f"(§6.2.5.6/6.2.7.6): line {i} tag '{tags[i]}' is not "
                    f"greater than previous tag '{tags[i - 1]}'."
                )
    else:
        sort_keys: list[str] = [_epoch_sort_key(t) for t in tags]
        for i in range(1, len(sort_keys)):
            if sort_keys[i] <= sort_keys[i - 1]:
                raise ValueError(
                    f"{block_name} data_lines must be strictly increasing "
                    f"(§6.2.5.6/6.2.7.6): line {i} tag '{tags[i]}' is not "
                    f"greater than previous tag '{tags[i - 1]}'."
                )


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
    """

    class Header(BaseModel):
        """OCM header block (CCSDS 502.0-B-3 table 6-1).

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID.
        """

        ccsds_ocm_vers: Annotated[
            str,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OCM_VERS"),
        ]

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (allowed in the OCM Header only immediately after "
                    "the OCM version number). See 7.8 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

        classification: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "User-defined free-text message classification/caveats of "
                    "this OCM. Values should be pre-coordinated between exchanging "
                    "entities by mutual agreement."
                ),
            ),
            FieldMetadata(keyword="CLASSIFICATION"),
        ] = None

        creation_date: Annotated[
            str,
            Field(
                description=(
                    "File creation date/time in UTC. "
                    "Accepts calendar (YYYY-MM-DDThh:mm:ss[Z]) and "
                    "day-of-year (YYYY-DOYThh:mm:ss[Z]) formats per CCSDS 7.5.10."
                ),
            ),
            FieldMetadata(keyword="CREATION_DATE"),
        ]

        originator: Annotated[
            str,
            Field(
                description=(
                    "Creating agency or operator. "
                    "Prefer the Abbreviation column from the SANA Registry of Organizations "
                    "(Annex B1, https://sanaregistry.org/r/organizations), "
                    "or the Name column when no abbreviation is listed."
                ),
            ),
            FieldMetadata(keyword="ORIGINATOR"),
        ]

        message_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "ID that uniquely identifies a message from a given originator. "
                    "Format and content are at the originator's discretion."
                ),
            ),
            FieldMetadata(keyword="MESSAGE_ID"),
        ] = None

        @field_validator("ccsds_ocm_vers")
        @classmethod
        def validate_version(cls, v: str) -> str:
            if not re.fullmatch(r"\d+\.\d+", v):
                raise ValueError("ccsds_ocm_vers must be in 'x.y' form, e.g. '3.0'")
            return v

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("creation_date")
        @classmethod
        def validate_creation_date(cls, v: str) -> str:
            return _validate_ccsds_date(v, "creation_date")


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

        _delineation: ClassVar[Delineation] = Delineation("META_START", "META_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (allowed only at the beginning of the OCM Metadata). "
                    "See 7.8 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

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
                    "Free-text comma-delimited field containing alternate name(s) of "
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
                description="Originator or programmatic Point-of-Contact (PoC) for OCM.",
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
                    "Originator's physical address (suggest comma-delimited address lines)."
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
                    "Creating agency or operator (value drawn from the SANA Organizations registry)."
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
                    "Technical PoC physical address (suggest comma-delimited address lines)."
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
                    "Unique identifier of Attitude Data Message(s) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="ADM_MSG_LINK"),
        ] = None

        cdm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Conjunction Data Message(s) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="CDM_MSG_LINK"),
        ] = None

        prm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Pointing Request Message(s) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="PRM_MSG_LINK"),
        ] = None

        rdm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Unique identifier of Reentry Data Message(s) linked to this OCM."
                ),
            ),
            FieldMetadata(keyword="RDM_MSG_LINK"),
        ] = None

        tdm_msg_link: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Comma-separated list of file name(s) and/or identification number(s) "
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
            ObjectType | None,
            Field(
                default=None,
                description=(
                    "Type of object. Select from annex B, subsection B11 "
                    "(https://sanaregistry.org/r/object_types)."
                ),
            ),
            FieldMetadata(keyword="OBJECT_TYPE"),
        ] = None

        # Time system - mandatory
        time_system: Annotated[
            TimeSystem,
            Field(
                description=(
                    "Time system for all absolute time stamps in this OCM including "
                    "EPOCH_TZERO. Select from annex B, subsection B3. Default is UTC. "
                    "If SCLK is selected, SCLK_OFFSET_AT_EPOCH and SCLK_SEC_PER_SI_SEC "
                    "shall be supplied."
                ),
            ),
            FieldMetadata(keyword="TIME_SYSTEM"),
        ]

        # Epoch - mandatory
        epoch_tzero: Annotated[
            str,
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
            OperationalStatus | None,
            Field(
                default=None,
                description=(
                    "Operational status of the space object. Select from annex B, "
                    "subsection B12 (https://sanaregistry.org/r/operational_status)."
                ),
            ),
            FieldMetadata(keyword="OPS_STATUS"),
        ] = None

        orbit_category: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Type of orbit. Select from annex B, subsection B14 "
                    "(https://sanaregistry.org/r/orbit_categories). "
                    "Examples: GEO, LEO, MEO, HEO, SUPER-GEO."
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
                    "Repeated entries (e.g., ORB, ORB) indicate multiple blocks of that type."
                ),
            ),
            FieldMetadata(keyword="OCM_DATA_ELEMENTS"),
        ] = None

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
            FieldMetadata(keyword="SCLK_OFFSET_AT_EPOCH", units="s"),
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
            FieldMetadata(keyword="SCLK_SEC_PER_SI_SEC", units="s"),
        ] = None

        # Message epoch linkage
        previous_message_epoch: Annotated[
            str | None,
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
            str | None,
            Field(
                default=None,
                description=(
                    "Anticipated (or actual) epoch of the next message from this originator "
                    "for this space object. May be provided without NEXT_MESSAGE_ID. "
                    "See 7.5.10 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="NEXT_MESSAGE_EPOCH"),
        ] = None

        # Coverage times (relative or absolute)
        start_time: Annotated[
            str | None,
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
            str | None,
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
                    "Defined as (STOP_TIME - START_TIME) in days."
                ),
            ),
            FieldMetadata(keyword="TIME_SPAN", units="d"),
        ] = None

        # Time correction / leap second data
        taimutc_at_tzero: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Difference (TAI – UTC) in seconds (total leap seconds since 1958) "
                    "as modeled by the originator at EPOCH_TZERO. [s]"
                ),
            ),
            FieldMetadata(keyword="TAIMUTC_AT_TZERO", units="s"),
        ] = None

        next_leap_epoch: Annotated[
            str | None,
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
                    "Difference (TAI – UTC) in seconds after the next leap second "
                    "at NEXT_LEAP_EPOCH. [s] "
                    "Should be provided when NEXT_LEAP_EPOCH is supplied."
                ),
            ),
            FieldMetadata(keyword="NEXT_LEAP_TAIMUTC", units="s"),
        ] = None

        ut1mutc_at_tzero: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Difference (UT1 – UTC) in seconds as modeled by the originator "
                    "at EPOCH_TZERO. [s]"
                ),
            ),
            FieldMetadata(keyword="UT1MUTC_AT_TZERO", units="s"),
        ] = None

        # Earth orientation / ephemeris sources
        eop_source: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Source and version of the originator's Earth Orientation Parameters "
                    "(including leap seconds, TAI - UT1, etc.)."
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

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("epoch_tzero")
        @classmethod
        def validate_epoch_tzero(cls, v: str) -> str:
            return _validate_ccsds_date(v, "epoch_tzero")

        @field_validator(
            "previous_message_epoch",
            "next_message_epoch",
            "next_leap_epoch",
            mode="before",
        )
        @classmethod
        def validate_optional_dates(cls, v: str | None, info: FieldValidationInfo) -> str | None:
            if v is not None:
                return _validate_ccsds_date(v, info.field_name)
            return v

        @field_validator("start_time", "stop_time", mode="before")
        @classmethod
        def validate_optional_time_tags(cls, v: str | None, info: FieldValidationInfo) -> str | None:
            if v is not None:
                return _validate_time_tag(v, info.field_name)
            return v

        @model_validator(mode="after")
        def check_sclk_fields_required(self) -> "OCM.Metadata":
            if self.time_system == TimeSystem.SCLK:
                if self.sclk_offset_at_epoch is None:
                    raise ValueError(
                        "sclk_offset_at_epoch is required when time_system='SCLK'."
                    )
                if self.sclk_sec_per_si_sec is None:
                    raise ValueError(
                        "sclk_sec_per_si_sec is required when time_system='SCLK'."
                    )
            return self

    # -----------------------------------------------------------------------
    # Trajectory State Time History (table 6-4)
    # -----------------------------------------------------------------------

    class TrajectoryStateTimeHistory(BaseModel):
        """
        One trajectory state time history data block, delimited by
        TRAJ_START / TRAJ_STOP in KVN (6.2.5).

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
        At least one data line is required (table 6-4: '…<Insert trajectory state
        time history here>' is marked M).
        """

        _delineation: ClassVar[Delineation] = Delineation("TRAJ_START", "TRAJ_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after TRAJ_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

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
            Interpolation | None,
            Field(
                default=None,
                description=(
                    "Recommended interpolation method. One of: HERMITE, LAGRANGE, LINEAR, "
                    "PROPAGATE (§6.2.5, table 6-4). "
                    "INTERPOLATION_DEGREE must be provided if set to anything other than PROPAGATE."
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
                    "Mandatory when INTERPOLATION is set and not 'PROPAGATE' (table 6-4)."
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
                    "(select from annex B, subsection B2, https://sanaregistry.org/r/orbit_centers) "
                    "or another reference frame center such as a spacecraft or formation-flying "
                    "reference. Natural bodies resolve to CenterName enum members; other centers "
                    "are accepted as plain strings. Default EARTH."
                ),
            ),
            FieldMetadata(keyword="CENTER_NAME"),
        ]

        traj_ref_frame: Annotated[
            RefFrame,
            Field(
                description=(
                    "Reference frame of the trajectory state time history. "
                    "Select from annex B, subsection B4 "
                    "(https://sanaregistry.org/r/celestial_body_reference_frames). "
                    "Default ICRF3."
                ),
            ),
            FieldMetadata(keyword="TRAJ_REF_FRAME"),
        ]

        traj_frame_epoch: Annotated[
            str | None,
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
            str | None,
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
            str | None,
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
            int | None,
            Field(
                default=None,
                description=(
                    "Basis for the orbit revolution counter. "
                    "0 = first launch/deployment corresponds to revolution 0.XXXX; "
                    "1 = first launch/deployment corresponds to revolution 1.XXXX. "
                    "Default 0. Shall be provided when ORB_REVNUM is specified."
                ),
            ),
            FieldMetadata(keyword="ORB_REVNUM_BASIS"),
        ] = None

        traj_type: Annotated[
            OrbitalElements,
            Field(
                description=(
                    "Trajectory state type. Select from annex B, subsection B7 "
                    "(https://sanaregistry.org/r/orbital_elements). Default CARTPV."
                ),
            ),
            FieldMetadata(keyword="TRAJ_TYPE"),
        ]

        orb_averaging: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Whether elements are osculating or mean, and if mean, which theory. "
                    "Select from annex B, subsection B13 "
                    "(https://sanaregistry.org/r/orbit_averaging). "
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
                    "by TRAJ_TYPE. At least one record is required (6.2.5.11). "
                    "Each line must be time-ordered (monotonically increasing) per 6.2.5.6."
                ),
            ),
        ]

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("traj_frame_epoch", mode="before")
        @classmethod
        def validate_traj_frame_epoch(cls, v: str | None) -> str | None:
            if v is not None:
                return _validate_ccsds_date(v, "traj_frame_epoch")
            return v

        @field_validator("useable_start_time", "useable_stop_time", mode="before")
        @classmethod
        def validate_useable_times(cls, v: str | None, info: FieldValidationInfo) -> str | None:
            if v is not None:
                return _validate_time_tag(v, info.field_name)
            return v

        @field_validator("orb_revnum_basis")
        @classmethod
        def validate_orb_revnum_basis_value(cls, v: int | None) -> int | None:
            if v is not None and v not in (0, 1):
                raise ValueError("orb_revnum_basis must be 0 or 1.")
            return v

        @model_validator(mode="after")
        def check_interpolation_degree_required(self) -> "OCM.TrajectoryStateTimeHistory":
            if (
                self.interpolation is not None
                and self.interpolation != Interpolation.PROPAGATE
                and self.interpolation_degree is None
            ):
                raise ValueError(
                    "interpolation_degree is required when interpolation is set "
                    "and not 'PROPAGATE' (table 6-4)."
                )
            return self

        @model_validator(mode="after")
        def check_orb_revnum_basis_required(self) -> "OCM.TrajectoryStateTimeHistory":
            if self.orb_revnum is not None and self.orb_revnum_basis is None:
                raise ValueError(
                    "orb_revnum_basis shall be provided when orb_revnum is specified (table 6-4)."
                )
            return self

        @model_validator(mode="after")
        def check_data_lines_ordered(self) -> "OCM.TrajectoryStateTimeHistory":
            """Validate trajectory state time history is strictly ordered (§6.2.5.6, §6.2.2.4)."""
            _check_data_lines_ordered(self.data_lines, "trajectory state")
            return self

    # -----------------------------------------------------------------------
    # Physical Properties (table 6-5)
    # -----------------------------------------------------------------------

    class SpaceObjectPhysicalCharacteristics(BaseModel):
        """
        Space Object Physical Characteristics block, delimited by
        PHYS_START / PHYS_STOP. At most one shall appear in an OCM (6.2.6.2).

        All fields are optional except the delimiters.

        OEB_PARENT_FRAME is conditional: shall be provided if OEB_Q1/Q2/Q3/QC
        are specified.
        OEB_PARENT_FRAME_EPOCH is conditional: required when OEB_PARENT_FRAME
        is provided and its epoch is not intrinsic to the frame definition.
        """

        _delineation: ClassVar[Delineation] = Delineation("PHYS_START", "PHYS_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after PHYS_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

        manufacturer: Annotated[
            str | None,
            Field(default=None, description="Satellite manufacturer's name."),
            FieldMetadata(keyword="MANUFACTURER"),
        ] = None

        bus_model: Annotated[
            str | None,
            Field(default=None, description="Satellite manufacturer's spacecraft bus model name."),
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
                    "Attitude-independent drag cross-sectional area (AD) facing the relative "
                    "wind vector, not included in AREA_ALONG_OEB parameters. [m**2]"
                ),
            ),
            FieldMetadata(keyword="DRAG_CONST_AREA", units="m**2"),
        ] = None

        drag_coeff_nom: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Nominal drag coefficient (CD_NOM). If 0, no atmospheric drag considered."
                ),
            ),
            FieldMetadata(keyword="DRAG_COEFF_NOM"),
        ] = None

        drag_uncertainty: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Drag coefficient 1σ percent uncertainty. [%] "
                    "Actual 1σ range = (1.0 ± DRAG_UNCERTAINTY/100.0) * CD_NOM."
                ),
            ),
            FieldMetadata(keyword="DRAG_UNCERTAINTY", units="%"),
        ] = None

        initial_wet_mass: Annotated[
            float | None,
            Field(
                default=None,
                description="Space object total mass at beginning of life. [kg]",
            ),
            FieldMetadata(keyword="INITIAL_WET_MASS", units="kg"),
        ] = None

        wet_mass: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Space object total mass including propellant at EPOCH_TZERO. [kg]"
                ),
            ),
            FieldMetadata(keyword="WET_MASS", units="kg"),
        ] = None

        dry_mass: Annotated[
            float | None,
            Field(
                default=None,
                description="Space object dry mass without propellant. [kg]",
            ),
            FieldMetadata(keyword="DRY_MASS", units="kg"),
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
            FieldMetadata(keyword="OEB_PARENT_FRAME"),
        ] = None

        oeb_parent_frame_epoch: Annotated[
            str | None,
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
                    "q1 = e1 * sin(φ/2) for rotation from OEB_PARENT_FRAME to OEB frame. "
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
                    "q2 = e2 * sin(φ/2) for rotation from OEB_PARENT_FRAME to OEB frame. "
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
                    "q3 = e3 * sin(φ/2) for rotation from OEB_PARENT_FRAME to OEB frame. "
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
                    "qc = cos(φ/2) for rotation from OEB_PARENT_FRAME to OEB frame. "
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
                description="Maximum physical dimension (along X_OEB) of the OEB. [m]",
            ),
            FieldMetadata(keyword="OEB_MAX", units="m"),
        ] = None

        oeb_int: Annotated[
            float | None,
            Field(
                default=None,
                description="Intermediate physical dimension (along y_OEB) of OEB. [m]",
            ),
            FieldMetadata(keyword="OEB_INT", units="m"),
        ] = None

        oeb_min: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum physical dimension (along z_OEB) of OEB. [m]",
            ),
            FieldMetadata(keyword="OEB_MIN", units="m"),
        ] = None

        # Attitude-dependent cross-sectional areas
        area_along_oeb_max: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-dependent cross-sectional area when viewed along max OEB (X_OEB). "
                    "Not included in DRAG_CONST_AREA or SRP_CONST_AREA. [m**2]"
                ),
            ),
            FieldMetadata(keyword="AREA_ALONG_OEB_MAX", units="m**2"),
        ] = None

        area_along_oeb_int: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-dependent cross-sectional area when viewed along intermediate "
                    "OEB (y_OEB). Not included in DRAG_CONST_AREA or SRP_CONST_AREA. [m**2]"
                ),
            ),
            FieldMetadata(keyword="AREA_ALONG_OEB_INT", units="m**2"),
        ] = None

        area_along_oeb_min: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-dependent cross-sectional area when viewed along minimum "
                    "OEB (z_OEB). Not included in DRAG_CONST_AREA or SRP_CONST_AREA. [m**2]"
                ),
            ),
            FieldMetadata(keyword="AREA_ALONG_OEB_MIN", units="m**2"),
        ] = None

        # Collision probability areas
        area_min_for_pc: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum cross-sectional area for collision probability estimation. [m**2]",
            ),
            FieldMetadata(keyword="AREA_MIN_FOR_PC", units="m**2"),
        ] = None

        area_max_for_pc: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum cross-sectional area for collision probability estimation. [m**2]",
            ),
            FieldMetadata(keyword="AREA_MAX_FOR_PC", units="m**2"),
        ] = None

        area_typ_for_pc: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile) cross-sectional area sampled over all orientations "
                    "for collision probability estimation. [m**2]"
                ),
            ),
            FieldMetadata(keyword="AREA_TYP_FOR_PC", units="m**2"),
        ] = None

        # Radar cross section
        rcs: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile) effective Radar Cross Section sampled over all "
                    "viewing angles. [m**2]"
                ),
            ),
            FieldMetadata(keyword="RCS", units="m**2"),
        ] = None

        rcs_min: Annotated[
            float | None,
            Field(
                default=None,
                description="Minimum Radar Cross Section observed for this object. [m**2]",
            ),
            FieldMetadata(keyword="RCS_MIN", units="m**2"),
        ] = None

        rcs_max: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum Radar Cross Section observed for this object. [m**2]",
            ),
            FieldMetadata(keyword="RCS_MAX", units="m**2"),
        ] = None

        # Solar radiation pressure
        srp_const_area: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Attitude-independent solar radiation pressure cross-sectional area (AR) "
                    "facing the Sun, not included in AREA_ALONG_OEB parameters. [m**2]"
                ),
            ),
            FieldMetadata(keyword="SRP_CONST_AREA", units="m**2"),
        ] = None

        solar_rad_coeff: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Nominal Solar Radiation Pressure Coefficient (CR_NOM). "
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
                    "SRP 1σ percent uncertainty. [%] "
                    "Actual 1σ range = (1.0 ± SRP_UNCERTAINTY/100.0) * CR_NOM."
                ),
            ),
            FieldMetadata(keyword="SOLAR_RAD_UNCERTAINTY", units="%"),
        ] = None

        # Visual magnitude
        vm_absolute: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile) absolute Visual Magnitude normalized to 1 AU "
                    "Sun-to-target, 0° phase angle, 40,000 km target-to-sensor distance."
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
                description="Typical (50th percentile) apparent Visual Magnitude observed.",
            ),
            FieldMetadata(keyword="VM_APPARENT"),
        ] = None

        vm_apparent_max: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Maximum apparent Visual Magnitude observed (the lowest Vmag = brightest)."
                ),
            ),
            FieldMetadata(keyword="VM_APPARENT_MAX"),
        ] = None

        reflectance: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Typical (50th percentile) coefficient of reflectance over all viewing "
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
            FieldMetadata(keyword="ATT_KNOWLEDGE", units="deg"),
        ] = None

        att_control: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Accuracy of attitude control system to maintain attitude assuming "
                    "perfect knowledge (deadbands). [deg]"
                ),
            ),
            FieldMetadata(keyword="ATT_CONTROL", units="deg"),
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
            FieldMetadata(keyword="ATT_POINTING", units="deg"),
        ] = None

        # Maneuver capability
        avg_maneuver_freq: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Average maneuver frequency (number of orbit- or attitude-adjust "
                    "maneuvers per year). [#/yr]"
                ),
            ),
            FieldMetadata(keyword="AVG_MANEUVER_FREQ", units="#/yr"),
        ] = None

        max_thrust: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Maximum composite thrust in any single body-fixed direction. [N]"
                ),
            ),
            FieldMetadata(keyword="MAX_THRUST", units="N"),
        ] = None

        dv_bol: Annotated[
            float | None,
            Field(
                default=None,
                description="Total ΔV capability at beginning of life. [km/s]",
            ),
            FieldMetadata(keyword="DV_BOL", units="km/s"),
        ] = None

        dv_remaining: Annotated[
            float | None,
            Field(
                default=None,
                description="Total ΔV remaining for the spacecraft. [km/s]",
            ),
            FieldMetadata(keyword="DV_REMAINING", units="km/s"),
        ] = None

        # Moments of inertia
        ixx: Annotated[
            float | None,
            Field(
                default=None,
                description="Moment of inertia about the X-axis of the primary body frame. [kg*m**2]",
            ),
            FieldMetadata(keyword="IXX", units="kg*m**2"),
        ] = None

        iyy: Annotated[
            float | None,
            Field(
                default=None,
                description="Moment of inertia about the Y-axis. [kg*m**2]",
            ),
            FieldMetadata(keyword="IYY", units="kg*m**2"),
        ] = None

        izz: Annotated[
            float | None,
            Field(
                default=None,
                description="Moment of inertia about the Z-axis. [kg*m**2]",
            ),
            FieldMetadata(keyword="IZZ", units="kg*m**2"),
        ] = None

        ixy: Annotated[
            float | None,
            Field(
                default=None,
                description="Inertia cross product of the X & Y axes. [kg*m**2]",
            ),
            FieldMetadata(keyword="IXY", units="kg*m**2"),
        ] = None

        ixz: Annotated[
            float | None,
            Field(
                default=None,
                description="Inertia cross product of the X & Z axes. [kg*m**2]",
            ),
            FieldMetadata(keyword="IXZ", units="kg*m**2"),
        ] = None

        iyz: Annotated[
            float | None,
            Field(
                default=None,
                description="Inertia cross product of the Y & Z axes. [kg*m**2]",
            ),
            FieldMetadata(keyword="IYZ", units="kg*m**2"),
        ] = None

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("oeb_parent_frame_epoch", mode="before")
        @classmethod
        def validate_oeb_parent_frame_epoch(cls, v: str | None) -> str | None:
            if v is not None:
                return _validate_ccsds_date(v, "oeb_parent_frame_epoch")
            return v

        @model_validator(mode="after")
        def check_oeb_parent_frame_required(self) -> "OCM.SpaceObjectPhysicalCharacteristics":
            quaternion_fields: tuple[float | None, float | None, float | None, float | None] = (self.oeb_q1, self.oeb_q2, self.oeb_q3, self.oeb_qc)
            any_quaternion: bool = any(q is not None for q in quaternion_fields)
            if any_quaternion and self.oeb_parent_frame is None:
                raise ValueError(
                    "oeb_parent_frame shall be provided when any of "
                    "oeb_q1, oeb_q2, oeb_q3, oeb_qc are specified (table 6-5)."
                )
            return self

    # -----------------------------------------------------------------------
    # Covariance Time History (table 6-6)
    # -----------------------------------------------------------------------

    class CovarianceTimeHistory(BaseModel):
        """
        One covariance time history data block, delimited by
        COV_START / COV_STOP in KVN (6.2.7).

        COV_REF_FRAME, COV_TYPE, and COV_ORDERING are mandatory (table 6-6).

        COV_FRAME_EPOCH is conditional: required when the epoch is not intrinsic
        to the reference frame definition. The default is EPOCH_TZERO.

        data_lines contains the raw covariance lines as specified by COV_TYPE
        and COV_ORDERING. At least one data line is required (table 6-6).
        """

        _delineation: ClassVar[Delineation] = Delineation("COV_START", "COV_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after COV_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

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
            RefFrame | ManCovRefFrame,
            Field(
                description=(
                    "Reference frame of the covariance time history. "
                    "Select from annex B, subsections B4 and B5 "
                    "(https://sanaregistry.org/r/celestial_body_reference_frames, "
                    "https://sanaregistry.org/r/orbit_relative_reference_frames). "
                    "Default TNW_INERTIAL."
                ),
            ),
            FieldMetadata(keyword="COV_REF_FRAME"),
        ]

        cov_frame_epoch: Annotated[
            str | None,
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
            FieldMetadata(keyword="COV_CONFIDENCE", units="%"),
        ] = None

        cov_type: Annotated[
            OrbitalElements | CovarianceType,
            Field(
                description=(
                    "Covariance composition type. Select from SANA Registry of Orbital Elements "
                    "(annex B, subsection B7) or Covariance Representations (annex B, subsection B8). "
                    "Default CARTPV."
                ),
            ),
            FieldMetadata(keyword="COV_TYPE"),
        ]

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
        ]

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
                    "COV_TYPE and COV_ORDERING. At least one line is required (6.2.7.11b)."
                ),
            ),
        ]

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("cov_frame_epoch", mode="before")
        @classmethod
        def validate_cov_frame_epoch(cls, v: str | None) -> str | None:
            if v is not None:
                return _validate_ccsds_date(v, "cov_frame_epoch")
            return v

        @model_validator(mode="after")
        def check_data_lines_ordered(self) -> "OCM.CovarianceTimeHistory":
            """Validate covariance time history is strictly ordered (§6.2.7.6, §6.2.2.4)."""
            _check_data_lines_ordered(self.data_lines, "covariance")
            return self

    # -----------------------------------------------------------------------
    # Maneuver Specification (tables 6-7, 6-8, 6-9)
    # -----------------------------------------------------------------------

    class ManeuverSpecification(BaseModel):
        """
        One maneuver time history data block, delimited by
        MAN_START / MAN_STOP in KVN (6.2.8).

        MAN_ID, MAN_DEVICE_ID, MAN_REF_FRAME, DC_TYPE, and MAN_COMPOSITION
        are mandatory (table 6-7).

        MAN_FRAME_EPOCH is conditional: required when the epoch is not intrinsic
        to the reference frame definition.

        DC duty cycle fields are conditional on DC_TYPE (6.2.8.20.6–6.2.8.20.7):
        - DC_WIN_OPEN, DC_WIN_CLOSE, DC_EXEC_START, DC_EXEC_STOP, DC_REF_TIME,
          DC_TIME_PULSE_DURATION, DC_TIME_PULSE_PERIOD shall all be set when
          DC_TYPE ≠ 'CONTINUOUS'.
        - DC_REF_DIR, DC_BODY_FRAME, DC_BODY_TRIGGER, DC_PA_START_ANGLE,
          DC_PA_STOP_ANGLE additionally required when DC_TYPE = 'TIME_AND_ANGLE'.

        data_lines contains the raw maneuver lines as specified by MAN_COMPOSITION.
        At least one data line is required.

        Note on DC_REF_DIR and DC_BODY_TRIGGER: these are three-element space-delimited
        vectors. Per 7.6 they are stored as single strings (the three numbers on one line).
        """

        _delineation: ClassVar[Delineation] = Delineation("MAN_START", "MAN_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after MAN_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

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
                    "Basis of this maneuver time history data (§6.2.8, table 6-7). "
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
                    "Maneuver device identifier. 'ALL' = summed acceleration/ΔV/thrust of "
                    "any/all thrusters. 'DEPLOY' = maneuvers caused by deployments only. "
                    "Otherwise: free-text identifier for the specific thruster/device."
                ),
            ),
            FieldMetadata(keyword="MAN_DEVICE_ID"),
        ]

        man_prev_epoch: Annotated[
            str | None,
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
            str | None,
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
            str | None,
            Field(
                default=None,
                description=(
                    "Intention(s) of the maneuver as a comma-delimited list. "
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
                    "For future maneuvers, source of the orbit and/or attitude state(s) "
                    "upon which the maneuver is based. Free-text; consider TRAJ_ID or OD_ID."
                ),
            ),
            FieldMetadata(keyword="MAN_PRED_SOURCE"),
        ] = None

        man_ref_frame: Annotated[
            RefFrame | ManCovRefFrame,
            Field(
                description=(
                    "Reference frame in which all maneuver vector direction data is provided. "
                    "Select from annex B, subsections B4 and B5. "
                    "Must be the same for all data elements within this block."
                ),
            ),
            FieldMetadata(keyword="MAN_REF_FRAME"),
        ]

        man_frame_epoch: Annotated[
            str | None,
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
            CenterName | None,
            Field(
                default=None,
                description=(
                    "Origin of maneuver gravitational assist body. "
                    "Select from annex B, subsection B2 "
                    "(https://sanaregistry.org/r/orbit_centers)."
                ),
            ),
            FieldMetadata(keyword="GRAV_ASSIST_NAME"),
        ] = None

        dc_type: Annotated[
            DutyCycleType,
            Field(
                description=(
                    "Duty cycle type. One of: CONTINUOUS (default), TIME, TIME_AND_ANGLE. "
                    "If not CONTINUOUS, duty cycle fields are required (6.2.8.20.6–6.2.8.20.7)."
                ),
            ),
            FieldMetadata(keyword="DC_TYPE"),
        ]

        # Duty cycle fields - conditional on dc_type ≠ CONTINUOUS
        dc_win_open: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Start time of duty cycle-based maneuver window. "
                    "Absolute or relative time tag. Required when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_WIN_OPEN"),
        ] = None

        dc_win_close: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "End time of duty cycle-based maneuver window. "
                    "Absolute or relative time tag. Required when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_WIN_CLOSE"),
        ] = None

        dc_min_cycles: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Minimum number of 'ON' duty cycles (may override DC_EXEC_STOP). "
                    "Optional even when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_MIN_CYCLES"),
        ] = None

        dc_max_cycles: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Maximum number of 'ON' duty cycles (may override DC_EXEC_STOP). "
                    "Optional even when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_MAX_CYCLES"),
        ] = None

        dc_exec_start: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Start time of initial duty cycle execution sequence. "
                    "Absolute or relative time tag. Required when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_EXEC_START"),
        ] = None

        dc_exec_stop: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "End time of final duty cycle execution sequence. "
                    "Absolute or relative time tag. Required when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_EXEC_STOP"),
        ] = None

        dc_ref_time: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Reference time for the THRUST duty cycle. "
                    "Absolute or relative time tag. Required when DC_TYPE ≠ CONTINUOUS."
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
                    "Required when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_TIME_PULSE_DURATION", units="s"),
        ] = None

        dc_time_pulse_period: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Elapsed time between start of one pulse and start of the next. [s] "
                    "Must be ≥ DC_TIME_PULSE_DURATION. Required when DC_TYPE ≠ CONTINUOUS."
                ),
            ),
            FieldMetadata(keyword="DC_TIME_PULSE_PERIOD", units="s"),
        ] = None

        # Additional duty cycle fields for TIME_AND_ANGLE mode
        dc_ref_dir: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Reference vector direction in MAN_REF_FRAME (3-element space-delimited "
                    "vector string, per 7.6). Required when DC_TYPE = TIME_AND_ANGLE."
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
                    "vector string, per 7.6). Required when DC_TYPE = TIME_AND_ANGLE."
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
            FieldMetadata(keyword="DC_PA_START_ANGLE", units="deg"),
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
            FieldMetadata(keyword="DC_PA_STOP_ANGLE", units="deg"),
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
            list[str],
            Field(
                min_length=1,
                description=(
                    "Maneuver time history lines, each containing values as specified by "
                    "MAN_COMPOSITION. At least one data line is required (table 6-7)."
                ),
            ),
        ]

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("man_frame_epoch", mode="before")
        @classmethod
        def validate_man_frame_epoch(cls, v: str | None) -> str | None:
            if v is not None:
                return _validate_ccsds_date(v, "man_frame_epoch")
            return v

        @field_validator("man_prev_epoch", "man_next_epoch", "dc_win_open",
                         "dc_win_close", "dc_exec_start", "dc_exec_stop",
                         "dc_ref_time", mode="before")
        @classmethod
        def validate_optional_time_tags(cls, v: str | None, info: FieldValidationInfo) -> str | None:
            if v is not None:
                return _validate_time_tag(v, info.field_name)
            return v

        @field_validator("man_composition")
        @classmethod
        def validate_man_composition_has_one_time(cls, v: str) -> str:
            elements: list[str] = [e.strip().upper() for e in v.split(",")]
            time_specs: list[str] = [e for e in elements if e in ("TIME_ABSOLUTE", "TIME_RELATIVE")]
            if len(time_specs) != 1:
                raise ValueError(
                    "man_composition must contain exactly one time specification "
                    "(TIME_ABSOLUTE or TIME_RELATIVE) per 6.2.8.18."
                )

            # §6.2.8.15 — table 6-8 (propulsive) and 6-9 (deployment) not commingled.
            _TABLE_6_8: set[str] = {
                "TIME_ABSOLUTE", "TIME_RELATIVE", "MAN_DURA", "DELTA_MASS",
                "ACC_X", "ACC_Y", "ACC_Z", "ACC_INTERP", "ACC_MAG_SIGMA", "ACC_DIR_SIGMA",
                "DV_X", "DV_Y", "DV_Z", "DV_MAG_SIGMA", "DV_DIR_SIGMA",
                "THR_X", "THR_Y", "THR_Z", "THR_EFFIC", "THR_INTERP",
                "THR_ISP", "THR_MAG_SIGMA", "THR_DIR_SIGMA",
            }
            _TABLE_6_9: set[str] = {
                "TIME_ABSOLUTE", "TIME_RELATIVE",
                "DEPLOY_ID", "DEPLOY_DV_X", "DEPLOY_DV_Y", "DEPLOY_DV_Z",
                "DEPLOY_MASS", "DEPLOY_DV_SIGMA", "DEPLOY_DIR_SIGMA",
                "DEPLOY_DV_RATIO", "DEPLOY_DV_CDA",
            }
            _EXCLUSIVE_6_8: set[str] = _TABLE_6_8 - _TABLE_6_9
            _EXCLUSIVE_6_9: set[str] = _TABLE_6_9 - _TABLE_6_8
            has_6_8: bool = any(e in _EXCLUSIVE_6_8 for e in elements)
            has_6_9: bool = any(e in _EXCLUSIVE_6_9 for e in elements)
            if has_6_8 and has_6_9:
                raise ValueError(
                    "man_composition must not commingle fields from table 6-8 "
                    "(propulsive) and table 6-9 (deployment) per 6.2.8.15."
                )

            # §6.2.8.16 — values must appear in the order fixed in table 6-8 or 6-9.
            # Order is verified by checking that the position of each element in
            # the composition does not precede the position of any earlier element.
            _ORDER_6_8: list[str] = [
                "TIME_ABSOLUTE", "TIME_RELATIVE", "MAN_DURA", "DELTA_MASS",
                "ACC_X", "ACC_Y", "ACC_Z", "ACC_INTERP", "ACC_MAG_SIGMA", "ACC_DIR_SIGMA",
                "DV_X", "DV_Y", "DV_Z", "DV_MAG_SIGMA", "DV_DIR_SIGMA",
                "THR_X", "THR_Y", "THR_Z", "THR_EFFIC", "THR_INTERP",
                "THR_ISP", "THR_MAG_SIGMA", "THR_DIR_SIGMA",
            ]
            _ORDER_6_9: list[str] = [
                "TIME_ABSOLUTE", "TIME_RELATIVE",
                "DEPLOY_ID", "DEPLOY_DV_X", "DEPLOY_DV_Y", "DEPLOY_DV_Z",
                "DEPLOY_MASS", "DEPLOY_DV_SIGMA", "DEPLOY_DIR_SIGMA",
                "DEPLOY_DV_RATIO", "DEPLOY_DV_CDA",
            ]
            order: list[str] = _ORDER_6_9 if has_6_9 else _ORDER_6_8
            pos_map: dict[str, int] = {kw: i for i, kw in enumerate(order)}
            positions: list[int] = [pos_map[e] for e in elements if e in pos_map]
            if positions != sorted(positions):
                raise ValueError(
                    "man_composition elements must appear in the order defined in "
                    "table 6-8 (propulsive) or table 6-9 (deployment) per 6.2.8.16."
                )

            return v

        @model_validator(mode="after")
        def check_dc_time_fields_required(self) -> "OCM.ManeuverSpecification":
            if self.dc_type in ("TIME", "TIME_AND_ANGLE"):
                required: dict[str, str | None] = {
                    "dc_win_open": self.dc_win_open,
                    "dc_win_close": self.dc_win_close,
                    "dc_exec_start": self.dc_exec_start,
                    "dc_exec_stop": self.dc_exec_stop,
                    "dc_ref_time": self.dc_ref_time,
                    "dc_time_pulse_duration": self.dc_time_pulse_duration,
                    "dc_time_pulse_period": self.dc_time_pulse_period,
                }
                missing: list[str] = [name for name, val in required.items() if val is None]
                if missing:
                    raise ValueError(
                        f"The following fields are required when dc_type='{self.dc_type}' "
                        f"(6.2.8.20.6): {', '.join(missing)}."
                    )
            return self

        @model_validator(mode="after")
        def check_dc_angle_fields_required(self) -> "OCM.ManeuverSpecification":
            if self.dc_type == "TIME_AND_ANGLE":
                required: dict[str, str | float | None] = {
                    "dc_ref_dir": self.dc_ref_dir,
                    "dc_body_frame": self.dc_body_frame,
                    "dc_body_trigger": self.dc_body_trigger,
                    "dc_pa_start_angle": self.dc_pa_start_angle,
                    "dc_pa_stop_angle": self.dc_pa_stop_angle,
                }
                missing: list[str] = [name for name, val in required.items() if val is None]
                if missing:
                    raise ValueError(
                        f"The following fields are required when dc_type='TIME_AND_ANGLE' "
                        f"(6.2.8.20.7): {', '.join(missing)}."
                    )
            return self

        @model_validator(mode="after")
        def check_pulse_period_ge_duration(self) -> "OCM.ManeuverSpecification":
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

        _delineation: ClassVar[Delineation] = Delineation("PERT_START", "PERT_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after PERT_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

        atmospheric_model: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Name of atmosphere model. Select from annex B, subsection B9 "
                    "(https://sanaregistry.org/r/atmosphere_models). "
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
                    "Gravity model name (from annex B, subsection B10) followed by degree (D) "
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
                description=(
                    "Oblate spheroid equatorial radius of the central body, if different "
                    "from the gravity model. [km]"
                ),
            ),
            FieldMetadata(keyword="EQUATORIAL_RADIUS", units="km"),
        ] = None

        gm: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Gravitational coefficient (G × central mass) of attracting body, "
                    "if different from the gravity model. [km**3/s**2]"
                ),
            ),
            FieldMetadata(keyword="GM", units="km**3/s**2"),
        ] = None

        n_body_perturbations: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "One or more N-body gravitational perturbation bodies, "
                    "comma-delimited. Values from annex B, subsection B2 (CENTER_NAME). "
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
            FieldMetadata(keyword="CENTRAL_BODY_ROTATION", units="deg/s"),
        ] = None

        oblate_flattening: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Central body's oblate spheroid oblateness. "
                    "For Earth ≈ 1/298.257223563 = 0.00335281066475."
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
                    "(e.g. DIURNAL, SEMI-DIURNAL). Free-text field."
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
                    "One of: NONE, CYLINDRICAL, CONE, DUAL_CONE (§6.2.9, table 6-10)."
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
            str | None,
            Field(
                default=None,
                description=(
                    "Epoch of the Space Weather data. "
                    "See 7.5.10 for formatting rules."
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
                    "(Kp, ap, Dst, F10.7, etc.). Free-text field. "
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
                    "Fixed (time-invariant) planetary geomagnetic index Kp. [nT] "
                    "Overrides normal time-varying Kp from SW_DATA_SOURCE."
                ),
            ),
            FieldMetadata(keyword="FIXED_GEOMAG_KP", units="nT"),
        ] = None

        fixed_geomag_ap: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) geomagnetic index ap. [nT] "
                    "Overrides normal time-varying ap from SW_DATA_SOURCE."
                ),
            ),
            FieldMetadata(keyword="FIXED_GEOMAG_AP", units="nT"),
        ] = None

        fixed_geomag_dst: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) planetary geomagnetic index Dst. [nT] "
                    "Overrides normal time-varying Dst from SW_DATA_SOURCE."
                ),
            ),
            FieldMetadata(keyword="FIXED_GEOMAG_DST", units="nT"),
        ] = None

        fixed_f10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) daily solar flux proxy F10.7. [SFU] "
                    "Overrides normal time-varying F10.7."
                ),
            ),
            FieldMetadata(keyword="FIXED_F10P7", units="SFU"),
        ] = None

        fixed_f10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) averaged solar flux proxy F10.7. [SFU] "
                    "Overrides normal time-varying averaged F10.7."
                ),
            ),
            FieldMetadata(keyword="FIXED_F10P7_MEAN", units="SFU"),
        ] = None

        fixed_m10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) daily solar flux proxy M10.7. [SFU]"
                ),
            ),
            FieldMetadata(keyword="FIXED_M10P7", units="SFU"),
        ] = None

        fixed_m10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) averaged solar flux proxy M10.7. [SFU]"
                ),
            ),
            FieldMetadata(keyword="FIXED_M10P7_MEAN", units="SFU"),
        ] = None

        fixed_s10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) daily solar flux proxy S10.7. [SFU]"
                ),
            ),
            FieldMetadata(keyword="FIXED_S10P7", units="SFU"),
        ] = None

        fixed_s10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) averaged solar flux proxy S10.7. [SFU]"
                ),
            ),
            FieldMetadata(keyword="FIXED_S10P7_MEAN", units="SFU"),
        ] = None

        fixed_y10p7: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) daily solar flux proxy Y10.7. [SFU]"
                ),
            ),
            FieldMetadata(keyword="FIXED_Y10P7", units="SFU"),
        ] = None

        fixed_y10p7_mean: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Fixed (time-invariant) averaged solar flux proxy Y10.7. [SFU]"
                ),
            ),
            FieldMetadata(keyword="FIXED_Y10P7_MEAN", units="SFU"),
        ] = None

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("sw_data_epoch", mode="before")
        @classmethod
        def validate_sw_data_epoch(cls, v: str | None) -> str | None:
            if v is not None:
                return _validate_ccsds_date(v, "sw_data_epoch")
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

        _delineation: ClassVar[Delineation] = Delineation("OD_START", "OD_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after OD_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

        od_id: Annotated[
            str,
            Field(
                description=(
                    "Identification number for this orbit determination. "
                    "Should match TRAJ_BASIS_ID, COV_BASIS_ID, and/or MAN_BASIS_ID "
                    "when those blocks reference this OD (6.2.10.6)."
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
                    "Common methods: BWLS (Batch Weighted Least Squares), EKF (Extended Kalman "
                    "Filter), SF (Sequential Filter), SRIF, SSEM."
                ),
            ),
            FieldMetadata(keyword="OD_METHOD"),
        ]

        od_epoch: Annotated[
            str,
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
                    "May be positive or negative (relative to OD_EPOCH, per 6.2.10.4)."
                ),
            ),
            FieldMetadata(keyword="DAYS_SINCE_FIRST_OBS", units="d"),
        ] = None

        days_since_last_obs: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Days elapsed between last accepted observation and OD_EPOCH. [d] "
                    "May be positive or negative (relative to OD_EPOCH, per 6.2.10.4)."
                ),
            ),
            FieldMetadata(keyword="DAYS_SINCE_LAST_OBS", units="d"),
        ] = None

        recommended_od_span: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Number of days of observations recommended for OD of the object. [d] "
                    "Useful only for Batch OD systems."
                ),
            ),
            FieldMetadata(keyword="RECOMMENDED_OD_SPAN", units="d"),
        ] = None

        actual_od_span: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Actual time span in days used for the OD. [d] "
                    "Should equal DAYS_SINCE_FIRST_OBS − DAYS_SINCE_LAST_OBS."
                ),
            ),
            FieldMetadata(keyword="ACTUAL_OD_SPAN", units="d"),
        ] = None

        obs_available: Annotated[
            int | None,
            Field(
                default=None,
                description="Number of observations available within the actual OD time span.",
            ),
            FieldMetadata(keyword="OBS_AVAILABLE"),
        ] = None

        obs_used: Annotated[
            int | None,
            Field(
                default=None,
                description="Number of observations accepted within the actual OD time span.",
            ),
            FieldMetadata(keyword="OBS_USED"),
        ] = None

        tracks_available: Annotated[
            int | None,
            Field(
                default=None,
                description="Number of sensor tracks available for OD within the actual time span.",
            ),
            FieldMetadata(keyword="TRACKS_AVAILABLE"),
        ] = None

        tracks_used: Annotated[
            int | None,
            Field(
                default=None,
                description="Number of sensor tracks accepted for OD within the actual time span.",
            ),
            FieldMetadata(keyword="TRACKS_USED"),
        ] = None

        maximum_obs_gap: Annotated[
            float | None,
            Field(
                default=None,
                description="Maximum time between observations in the OD. [d]",
            ),
            FieldMetadata(keyword="MAXIMUM_OBS_GAP", units="d"),
        ] = None

        od_epoch_eigmaj: Annotated[
            float | None,
            Field(
                default=None,
                description="Positional error ellipsoid 1σ major eigenvalue at OD epoch. [m]",
            ),
            FieldMetadata(keyword="OD_EPOCH_EIGMAJ", units="m"),
        ] = None

        od_epoch_eigint: Annotated[
            float | None,
            Field(
                default=None,
                description="Positional error ellipsoid 1σ intermediate eigenvalue at OD epoch. [m]",
            ),
            FieldMetadata(keyword="OD_EPOCH_EIGINT", units="m"),
        ] = None

        od_epoch_eigmin: Annotated[
            float | None,
            Field(
                default=None,
                description="Positional error ellipsoid 1σ minor eigenvalue at OD epoch. [m]",
            ),
            FieldMetadata(keyword="OD_EPOCH_EIGMIN", units="m"),
        ] = None

        od_max_pred_eigmaj: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Maximum predicted major eigenvalue of the 1σ positional error ellipsoid "
                    "over the entire TIME_SPAN of the OCM. [m]"
                ),
            ),
            FieldMetadata(keyword="OD_MAX_PRED_EIGMAJ", units="m"),
        ] = None

        od_min_pred_eigmin: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Minimum predicted minor eigenvalue of the 1σ positional error ellipsoid "
                    "over the entire TIME_SPAN of the OCM. [m]"
                ),
            ),
            FieldMetadata(keyword="OD_MIN_PRED_EIGMIN", units="m"),
        ] = None

        od_confidence: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "OD confidence metric spanning 0 to 100%. [%] "
                    "Useful only for Filter-based OD systems. "
                    "Defined by mutual agreement of message exchange participants."
                ),
            ),
            FieldMetadata(keyword="OD_CONFIDENCE", units="%"),
        ] = None

        gdop: Annotated[
            float | None,
            Field(
                default=None,
                description=(
                    "Generalized Dilution Of Precision for this OD, based on the "
                    "observability grammian (annex F, subsection F4). Ideal value ≈ 1.0."
                ),
            ),
            FieldMetadata(keyword="GDOP"),
        ] = None

        solve_n: Annotated[
            int | None,
            Field(
                default=None,
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
                    "(See annex F, subsection F7.)"
                ),
            ),
            FieldMetadata(keyword="SEDR", units="W/kg"),
        ] = None

        sensors_n: Annotated[
            int | None,
            Field(
                default=None,
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
                description=(
                    "Weighted RMS residual ratio (useful only for Batch OD systems). "
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

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("od_epoch")
        @classmethod
        def validate_od_epoch(cls, v: str) -> str:
            return _validate_time_tag(v, "od_epoch")

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

        _delineation: ClassVar[Delineation] = Delineation("USER_START", "USER_STOP")

        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (only immediately after USER_START). See 7.8."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

        user_defined: dict[str, str] = Field(
            default_factory=dict,
            description=(
                "User-defined parameters keyed by the suffix of USER_DEFINED_x. "
                "All parameters must be described in an ICD (6.2.11.1). "
                "At least one entry is required when this block is present."
            ),
        )

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @model_validator(mode="after")
        def check_user_defined_not_empty(self) -> "OCM.UserDefinedParameters":
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
        description=(
            "One or more trajectory state time history blocks (optional, repeatable). "
            "Each block is delimited by TRAJ_START / TRAJ_STOP. "
            "A corresponding perturbations section should be included (6.2.5.14)."
        ),
    )

    physical_characteristics: SpaceObjectPhysicalCharacteristics | None = Field(
        default=None,
        description=(
            "Space object physical characteristics block (optional, at most one). "
            "Delimited by PHYS_START / PHYS_STOP."
        ),
    )

    covariances: list[CovarianceTimeHistory] | None = Field(
        default=None,
        description=(
            "One or more covariance time history blocks (optional, repeatable). "
            "Each block is delimited by COV_START / COV_STOP. "
            "A corresponding perturbations section should be included (6.2.7.11a)."
        ),
    )

    maneuvers: list[ManeuverSpecification] | None = Field(
        default=None,
        description=(
            "One or more maneuver specification blocks (optional, repeatable). "
            "Each block is delimited by MAN_START / MAN_STOP."
        ),
    )

    perturbations: PerturbationsSpecification | None = Field(
        default=None,
        description=(
            "Perturbations specification block (conditional: required when an orbit "
            "determination section is included; recommended when trajectory state or "
            "covariance blocks are present). Delimited by PERT_START / PERT_STOP. "
            "At most one section shall appear in an OCM (6.2.9.2)."
        ),
    )

    orbit_determination: OrbitDeterminationData | None = Field(
        default=None,
        description=(
            "Orbit determination data block (optional, at most one). "
            "Delimited by OD_START / OD_STOP. "
            "When present, a perturbations section shall also be present (6.2.10.5)."
        ),
    )

    user_defined: UserDefinedParameters | None = Field(
        default=None,
        description=(
            "User-defined parameters block (optional, at most one). "
            "Delimited by USER_START / USER_STOP. "
            "All keywords must be described in an ICD."
        ),
    )

    # -----------------------------------------------------------------------
    # Top-level cross-block validators
    # -----------------------------------------------------------------------

    @model_validator(mode="after")
    def check_perturbations_required_for_od(self) -> "OCM":
        """
        If an orbit determination section is included, a corresponding
        perturbations section shall also be included (6.2.10.5).
        """
        if self.orbit_determination is not None and self.perturbations is None:
            raise ValueError(
                "A perturbations block (perturbations) is required when an orbit "
                "determination block (orbit_determination) is present (6.2.10.5)."
            )
        return self


OrbitComprehensiveMessage = OCM
