from __future__ import annotations

import re
from typing import Annotated
from typing import Any
from typing import ClassVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import FieldValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from .base import CCSDSDataMessage
from ._epoch import _epoch_sort_key
from ._epoch import _validate_ccsds_date
from .metadata import Delineation
from .metadata import FieldMetadata
from .values import CenterName
from .values import Interpolation
from .values import RefFrame
from .values import TimeSystem
from .values import ManCovRefFrame

# Frames whose epoch is intrinsic to the frame definition (shared with OPM/OMM).
# OEM allows TEME in REF_FRAME (not explicitly forbidden).
_EPOCH_INTRINSIC_FRAMES: set[RefFrame] = {
    RefFrame.EME2000,
    RefFrame.GCRF,
    RefFrame.GRC,
    RefFrame.ICRF,
    RefFrame.ITRF2000,
    RefFrame.ITRF_93,
    RefFrame.ITRF_97,
    RefFrame.MCI,
    RefFrame.TEME,
}


class OEM(CCSDSDataMessage, BaseModel):
    """
    Orbit Ephemeris Message (OEM).

    Orbit information may be exchanged between two participants by sending an ephemeris
    in the form of a series of state vectors (Cartesian vectors providing position and
    velocity, and optionally accelerations) using an OEM. The message recipient must
    have a means of interpolating across these state vectors to obtain the state at an
    arbitrary time contained within the span of the ephemeris.

    The OEM may be used for assessing mutual physical or electromagnetic interference
    among Earth-orbiting spacecraft, developing collaborative maneuvers, and
    representing the orbits of active satellites, inactive man-made objects, near-Earth
    debris fragments, etc. The OEM reflects the dynamic modeling of any users' approach
    to conservative and nonconservative phenomena.
    """

    class Header(BaseModel):
        """OEM header block (CCSDS 502.0-B-3 table 5-2).

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID. The header appears
        once at the top of the file, before the first segment.
        """

        ccsds_oem_vers: Annotated[
            str,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OEM_VERS"),
        ]

        # 7.8 Formatting rules
        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments (allowed in the OEM Header "
                    "only immediately after the OEM version number). "
                    "See 7.8 for formatting rules."
                ),
            ),
            FieldMetadata(keyword="COMMENT"),
        ] = None

        classification: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "User-defined free-text message classification/caveats "
                    "of this OEM. Values should be pre-coordinated between "
                    "exchanging entities by mutual agreement."
                ),
            ),
            FieldMetadata(keyword="CLASSIFICATION"),
        ] = None

        # 7.5.10 Formatting rules
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
                    "or the Name column when no abbreviation is listed. "
                    "Free-form strings are accepted; validation against the registry "
                    "is left to the application layer."
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

        @field_validator("ccsds_oem_vers")
        @classmethod
        def validate_version(cls, v: str) -> str:
            if not re.fullmatch(r"\d+\.\d+", v):
                raise ValueError("ccsds_oem_vers must be in 'x.y' form, e.g. '3.0'")
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

    class Segment(BaseModel):
        """One (Metadata + EphemerisData + optional CovarianceSection) block.

        The OEM body is a non-empty list of these segments (table 5-1).
        """

        class Metadata(BaseModel):
            """Per-segment metadata, delimited by META_START / META_STOP in KVN.

            The delimiters are a serialization concern, not a domain concern.
            """
            _delineation: ClassVar[Delineation] = Delineation("META_START", "META_STOP")

            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments (allowed in the OEM Metadata block "
                        "immediately after META_START). "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None

            object_name: Annotated[
                str,
                Field(
                    description=(
                        "Spacecraft name. Recommended to use UN OOSA designator index. "
                        "Set to 'UNKNOWN' if name is unknown or cannot be disclosed."
                    ),
                ),
                FieldMetadata(keyword="OBJECT_NAME"),
            ]

            object_id: Annotated[
                str,
                Field(
                    description=(
                        "International spacecraft designator. Recommended format: "
                        "YYYY-NNNP{PP}. Set to 'UNKNOWN' if unavailable."
                    ),
                ),
                FieldMetadata(keyword="OBJECT_ID"),
            ]

            center_name: Annotated[
                CenterName | str,
                Field(
                    description=(
                        "Origin of the OEM reference frame. May be a natural solar "
                        "system body (select from annex B, subsection B2) or another "
                        "reference frame center such as a spacecraft (use OBJECT_ID or "
                        "UN OOSA international designator per §5.2.3). "
                        "Natural bodies resolve to CenterName enum members; spacecraft "
                        "IDs are accepted as plain strings."
                    ),
                ),
                FieldMetadata(keyword="CENTER_NAME"),
            ]

            ref_frame: Annotated[
                RefFrame,
                Field(
                    description=(
                        "Reference frame in which the ephemeris data are given. "
                        "Values outside 3.2.3.3 should be documented in an ICD."
                    ),
                ),
                FieldMetadata(keyword="REF_FRAME"),
            ]

            ref_frame_epoch: Annotated[
                str | None,
                Field(
                    default=None,
                    description=(
                        "Epoch of the reference frame. Mandatory when the epoch is not "
                        "intrinsic to the frame definition. CCSDS date/time format per 7.5.10."
                    ),
                ),
                FieldMetadata(keyword="REF_FRAME_EPOCH"),
            ] = None

            time_system: Annotated[
                TimeSystem,
                Field(
                    description=(
                        "Time system used for ephemeris and covariance data. "
                        "Must remain fixed across all segments (5.2.4.5). "
                        "Values outside 3.2.3.2 should be documented in an ICD."
                    ),
                ),
                FieldMetadata(keyword="TIME_SYSTEM"),
            ]

            start_time: Annotated[
                str,
                Field(
                    description=(
                        "Start of TOTAL time span covered by ephemeris and covariance data "
                        "immediately following this metadata block. See 7.5.10."
                    ),
                ),
                FieldMetadata(keyword="START_TIME"),
            ]

            useable_start_time: Annotated[
                str | None,
                Field(
                    default=None,
                    description=(
                        "Start of USEABLE time span. Optional; allows fictitious leading "
                        "nodes for interpolation methods requiring more than two nodes. "
                        "Must be within [start_time, stop_time]. See 7.5.10."
                    ),
                ),
                FieldMetadata(keyword="USEABLE_START_TIME"),
            ] = None

            useable_stop_time: Annotated[
                str | None,
                Field(
                    default=None,
                    description=(
                        "Stop of USEABLE time span. Optional; allows fictitious trailing "
                        "nodes for interpolation methods requiring more than two nodes. "
                        "Must be within [start_time, stop_time]. Useable intervals across "
                        "consecutive segments must not overlap (except a shared endpoint). "
                        "See 7.5.10."
                    ),
                ),
                FieldMetadata(keyword="USEABLE_STOP_TIME"),
            ] = None

            stop_time: Annotated[
                str,
                Field(
                    description=(
                        "End of TOTAL time span covered by ephemeris and covariance data "
                        "immediately following this metadata block. See 7.5.10."
                    ),
                ),
                FieldMetadata(keyword="STOP_TIME"),
            ]

            interpolation: Annotated[
                Interpolation | None,
                Field(
                    default=None,
                    description=(
                        "Recommended interpolation method for ephemeris data. "
                        "One of: HERMITE, LAGRANGE, LINEAR (§5.2.3, table 5-3). "
                        "PROPAGATE is OCM-only and is rejected here. "
                        "interpolation_degree must be provided when set."
                    ),
                ),
                FieldMetadata(keyword="INTERPOLATION"),
            ] = None

            interpolation_degree: Annotated[
                int | None,
                Field(
                    default=None,
                    description=(
                        "Recommended interpolation degree. Integer. "
                        "Mandatory when interpolation is set (5.2.3, table 5-3)."
                    ),
                ),
                FieldMetadata(keyword="INTERPOLATION_DEGREE"),
            ] = None

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            # The spec explicitly says "there is no CCSDS-based restriction on the value
            # for this keyword" and calls the YYYY-NNNP{PP} format a recommendation.

            @field_validator("ref_frame_epoch", "start_time", "stop_time",
                             "useable_start_time", "useable_stop_time",
                             mode="before")
            @classmethod
            def validate_time_fields(cls, v: str | None, info: FieldValidationInfo) -> str | None:
                if v is None:
                    return v
                return _validate_ccsds_date(v, info.field_name)
 
            @model_validator(mode="after")
            def check_ref_frame_epoch_required(self) -> "OEM.Segment.Metadata":
                if (
                    self.ref_frame not in _EPOCH_INTRINSIC_FRAMES
                    and self.ref_frame_epoch is None
                ):
                    raise ValueError(
                        f"ref_frame_epoch is required when ref_frame='{self.ref_frame}' "
                        f"because its epoch is not intrinsic to the frame definition."
                    )
                return self
 
            @model_validator(mode="after")
            def check_interpolation_not_propagate(self) -> "OEM.Segment.Metadata":
                if self.interpolation == Interpolation.PROPAGATE:
                    raise ValueError(
                        "INTERPOLATION=PROPAGATE is not valid for OEM; "
                        "allowed values are HERMITE, LAGRANGE, LINEAR (§5.2.3)."
                    )
                return self

            @model_validator(mode="after")
            def check_interpolation_degree_required(self) -> "OEM.Segment.Metadata":
                if self.interpolation is not None and self.interpolation_degree is None:
                    raise ValueError(
                        "interpolation_degree is required when interpolation is set "
                        "(table 5-3)."
                    )
                return self
 
            @model_validator(mode="after")
            def check_useable_times_within_total_span(self) -> "OEM.Segment.Metadata":
                """Validate useable start/stop lie within [start_time, stop_time].

                §7.5.10 allows two epoch formats (calendar and DOY); _epoch_sort_key
                normalizes both to calendar format before comparison.
                """
                if self.useable_start_time is not None:
                    if _epoch_sort_key(self.useable_start_time) < _epoch_sort_key(self.start_time):
                        raise ValueError(
                            "useable_start_time must not be earlier than start_time."
                        )
                    if _epoch_sort_key(self.useable_start_time) > _epoch_sort_key(self.stop_time):
                        raise ValueError(
                            "useable_start_time must not be later than stop_time."
                        )
                if self.useable_stop_time is not None:
                    if _epoch_sort_key(self.useable_stop_time) > _epoch_sort_key(self.stop_time):
                        raise ValueError(
                            "useable_stop_time must not be later than stop_time."
                        )
                    if _epoch_sort_key(self.useable_stop_time) < _epoch_sort_key(self.start_time):
                        raise ValueError(
                            "useable_stop_time must not be earlier than start_time."
                        )
                if (self.useable_start_time is not None
                    and self.useable_stop_time is not None
                    and _epoch_sort_key(self.useable_start_time) > _epoch_sort_key(self.useable_stop_time)):
                        raise ValueError(
                            "useable_start_time must not be later than useable_stop_time."
                        )
                return self

            @model_validator(mode="after")
            def check_start_before_stop(self) -> "OEM.Segment.Metadata":
                if _epoch_sort_key(self.start_time) >= _epoch_sort_key(self.stop_time):
                    raise ValueError("start_time must be earlier than stop_time.")
                return self

        class EphemerisData(BaseModel):
            """The list of ephemeris data lines for one segment.

            ``comment`` is allowed only at the beginning of the ephemeris data section
            (7.8.9); it must not appear between data lines.
            ``ephemeris_data_lines`` must be non-empty and ordered by increasing epoch.
            """
            
            # Each set of ephemeris data, including the time tag, must be provided on
            # a single line. The order in which data items are given shall be fixed:
            #     Epoch, X, Y, Z, X_DOT, Y_DOT, Z_DOT, X_DDOT, Y_DDOT, Z_DDOT.
            #
            # At least one space character must be used to separate the items in each
            # ephemeris data line.
            class EphemerisDataLine(BaseModel):
                """One ephemeris data line: epoch + position + velocity + optional acceleration.

                Acceleration is all-or-nothing: if any component is provided, all three
                must be provided (5.2.4.1–5.2.4.2).
                Units: position [km], velocity [km/s], acceleration [km/s**2] (7.7.2.1).
                Units are not displayed in OEM data lines.
                """
                epoch: Annotated[
                    str,
                    Field(
                        description=(
                            "Epoch of this state vector. See 7.5.10."
                        ),
                    ),
                    FieldMetadata(keyword="EPOCH"),
                ]
    
                x: Annotated[
                    float,
                    Field(
                        description=(
                            "Position vector X-component. [km]"
                        ),
                    ),
                    FieldMetadata(keyword="X", units="km", format_spec=" .3f"),
                ]

                y: Annotated[
                    float,
                    Field(
                        description=(
                            "Position vector Y-component. [km]"
                        ),
                    ),
                    FieldMetadata(keyword="Y", units="km", format_spec=" .3f"),
                ]

                z: Annotated[
                    float,
                    Field(
                        description=(
                            "Position vector Z-component. [km]"
                        ),
                    ),
                    FieldMetadata(keyword="Z", units="km", format_spec=" .3f"),
                ]

                x_dot: Annotated[
                    float,
                    Field(description=(
                        "Velocity vector X-component. [km/s]"
                        ),
                    ),
                    FieldMetadata(keyword="X_DOT", units="km/s", format_spec=" .5f"),
                ]

                y_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Velocity vector Y-component. [km/s]"
                        ),
                    ),
                    FieldMetadata(keyword="Y_DOT", units="km/s", format_spec=" .5f"),
                ]

                z_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Velocity vector Z-component. [km/s]"
                        ),
                    ),
                    FieldMetadata(keyword="Z_DOT", units="km/s", format_spec=" .5f"),
                ]

                x_ddot: Annotated[
                    float | None,
                    Field(
                        default=None,
                        description=(
                            "Acceleration vector X-component. [km/s**2] "
                            "Must be provided together with y_ddot and z_ddot, or not at all."
                        ),
                    ),
                    FieldMetadata(keyword="X_DDOT", units="km/s**2", format_spec=" .1e"),
                ] = None

                y_ddot: Annotated[
                    float | None,
                    Field(
                        default=None,
                        description=(
                            "Acceleration vector Y-component. [km/s**2] "
                            "Must be provided together with x_ddot and z_ddot, or not at all."
                        ),
                    ),
                    FieldMetadata(keyword="Y_DDOT", units="km/s**2", format_spec=" .1e"),
                ] = None

                z_ddot: Annotated[
                    float | None,
                    Field(
                        default=None,
                        description=(
                            "Acceleration vector Z-component. [km/s**2] "
                            "Must be provided together with x_ddot and y_ddot, or not at all."
                        ),
                    ),
                    FieldMetadata(keyword="Z_DDOT", units="km/s**2", format_spec=" .1e"),
                ] = None
    
                @field_validator("epoch")
                @classmethod
                def validate_epoch(cls, v: str) -> str:
                    return _validate_ccsds_date(v, "epoch")
    
                @model_validator(mode="after")
                def check_acceleration_all_or_nothing(self) -> "OEM.Segment.EphemerisData.EphemerisDataLine":
                    components: tuple[float | None, float | None, float | None] = (self.x_ddot, self.y_ddot, self.z_ddot)
                    present: list[float] = [c for c in components if c is not None]
                    if present and len(present) != 3:
                        raise ValueError(
                            "Acceleration components are all-or-nothing: provide all three "
                            "(x_ddot, y_ddot, z_ddot) or none (5.2.4.1-5.2.4.2)."
                        )
                    return self
            
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments (allowed at the beginning of the OEM data section "
                        "only; must not appear between data lines, per §7.8.9). "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None

            ephemeris_data_lines: Annotated[
                list["OEM.Segment.EphemerisData.EphemerisDataLine"],
                Field(
                    min_length=1,
                    description=(
                        "Ordered list of ephemeris data lines (increasing epoch). "
                        "At least one record is required."
                    ),
                ),
            ]

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            @model_validator(mode="after")
            def check_epochs_ordered(self) -> "OEM.Segment.EphemerisData":
                epochs: list[str] = [sv.epoch for sv in self.ephemeris_data_lines]
                for i, (prev_epoch, curr_epoch) in enumerate(zip(epochs, epochs[1:]), start=1):
                    if _epoch_sort_key(curr_epoch) <= _epoch_sort_key(prev_epoch):
                        raise ValueError(
                            f"Ephemeris data line epochs must be strictly increasing. "
                            f"Found epoch[{i}]='{curr_epoch}' <= epoch[{i-1}]='{prev_epoch}'."
                        )
                return self
 
            # ------------------------------------------------------------------
            # Computation shortcuts — one-line delegates, zero logic.
            # Removing these methods leaves EphemerisData fully functional.
            # ------------------------------------------------------------------

            def to_numpy(self) -> Any:
                """Convert to a (N, 6) or (N, 9) numpy array via NumpyBackend.

                Returns:
                    ndarray: float64 ndarray of shape (N, 6) without accelerations,
                    (N, 9) with.

                Raises:
                    ImportError: If numpy is not installed. Install with
                        ``pip install orbit-data-messages[numpy]``.
                """
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().to_array(self)

            def to_ostk(self) -> Any:
                """Convert to an OSTk Trajectory object via OSTkBackend.

                Returns:
                    Any: An OSTk Trajectory built from this ephemeris data.

                Raises:
                    ImportError: If OSTk is not installed. Install with
                        ``pip install orbit-data-messages[ostk]``.
                """
                from orbit_data_messages.compute.backends.ostk_ import OSTkBackend
                return OSTkBackend().trajectory_from_ephemeris(self)

            @classmethod
            def from_numpy(cls, arr: Any, epochs: list[str]) -> "OEM.Segment.EphemerisData":
                """Construct a validated EphemerisData from a numpy array and epoch strings.

                Args:
                    arr (Any): float64 ndarray of shape (N, 6) or (N, 9).
                    epochs (list[str]): N CCSDS §7.5.10 epoch strings.

                Returns:
                    OEM.Segment.EphemerisData: A fully validated EphemerisData instance.

                Raises:
                    ImportError: If numpy is not installed. Install with
                        ``pip install orbit-data-messages[numpy]``.
                """
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().ephemeris_data_from_array(arr, epochs)

            @classmethod
            def from_ostk(cls, trajectory: Any) -> "OEM.Segment.EphemerisData":
                """Construct a validated EphemerisData from an OSTk Trajectory.

                Args:
                    trajectory (Any): An OSTk Trajectory object.

                Returns:
                    OEM.Segment.EphemerisData: A fully validated EphemerisData instance.

                Raises:
                    ImportError: If OSTk is not installed. Install with
                        ``pip install orbit-data-messages[ostk]``.
                """
                from orbit_data_messages.compute.backends.ostk_ import OSTkBackend
                return OSTkBackend().ephemeris_data_from_trajectory(trajectory)

        class CovarianceMatrix(BaseModel):
            """The optional covariance matrix block that follows an ephemeris data block.

            Delimited by COVARIANCE_START / COVARIANCE_STOP in KVN. Contains one or
            more ``CovarianceMatrixLines`` entries ordered by increasing epoch
            (5.2.5.6–5.2.5.7). ``comment`` is allowed only at the beginning (7.8.9).
            """

            class CovarianceMatrixLines(BaseModel):
                """A single covariance matrix entry within the covariance block.

                Each entry has its own EPOCH and optional COV_REF_FRAME, followed by
                the 21 lower-triangular elements (rows 1–6, left to right).
                Units: km**2, km**2/s, km**2/s**2 per 7.7.2.2 (not in data lines).
                """
                # 7.8 Formatting rules
                epoch: Annotated[
                    str,
                    Field(
                        description=(
                            "Epoch of this covariance matrix. See 7.5.10."
                        ),
                    ),
                    FieldMetadata(keyword="EPOCH"),
                ]
                
                cov_ref_frame: Annotated[
                    RefFrame | ManCovRefFrame | None,
                    Field(
                        default=None,
                        description=(
                            "Reference frame for this covariance matrix. "
                            "May be omitted if identical to the segment REF_FRAME. "
                            "Accepts values from 3.2.3.3 or 3.2.4.11 (table 5-4)."
                        ),
                    ),
                    FieldMetadata(keyword="COV_REF_FRAME"),
                ] = None

                # Row 1
                cx_x: Annotated[
                    float,
                    Field(description="Covariance matrix [1,1]. [km**2]"),
                    FieldMetadata(keyword="CX_X", units="km**2", format_spec=" .15e"),
                ]

                # Row 2
                cy_x: Annotated[
                    float,
                    Field(description="Covariance matrix [2,1]. [km**2]"),
                    FieldMetadata(keyword="CY_X", units="km**2", format_spec=" .15e"),
                ]

                cy_y: Annotated[
                    float,
                    Field(description="Covariance matrix [2,2]. [km**2]"),
                    FieldMetadata(keyword="CY_Y", units="km**2", format_spec=" .15e"),
                ]

                # Row 3
                cz_x: Annotated[
                    float,
                    Field(description="Covariance matrix [3,1]. [km**2]"),
                    FieldMetadata(keyword="CZ_X", units="km**2", format_spec=" .15e"),
                ]

                cz_y: Annotated[
                    float,
                    Field(description="Covariance matrix [3,2]. [km**2]"),
                    FieldMetadata(keyword="CZ_Y", units="km**2", format_spec=" .15e"),
                ]

                cz_z: Annotated[
                    float,
                    Field(description="Covariance matrix [3,3]. [km**2]"),
                    FieldMetadata(keyword="CZ_Z", units="km**2", format_spec=" .15e"),
                ]

                # Row 4
                cx_dot_x: Annotated[
                    float,
                    Field(description="Covariance matrix [4,1]. [km**2/s]"),
                    FieldMetadata(keyword="CX_DOT_X", units="km**2/s", format_spec=" .15e"),
                ]

                cx_dot_y: Annotated[
                    float,
                    Field(description="Covariance matrix [4,2]. [km**2/s]"),
                    FieldMetadata(keyword="CX_DOT_Y", units="km**2/s", format_spec=" .15e"),
                ]

                cx_dot_z: Annotated[
                    float,
                    Field(description="Covariance matrix [4,3]. [km**2/s]"),
                    FieldMetadata(keyword="CX_DOT_Z", units="km**2/s", format_spec=" .15e"),
                ]

                cx_dot_x_dot: Annotated[
                    float,
                    Field(description="Covariance matrix [4,4]. [km**2/s**2]"),
                    FieldMetadata(keyword="CX_DOT_X_DOT", units="km**2/s**2", format_spec=" .15e"),
                ]

                # Row 5
                cy_dot_x: Annotated[
                    float,
                    Field(description="Covariance matrix [5,1]. [km**2/s]"),
                    FieldMetadata(keyword="CY_DOT_X", units="km**2/s", format_spec=" .15e"),
                ]

                cy_dot_y: Annotated[
                    float,
                    Field(description="Covariance matrix [5,2]. [km**2/s]"),
                    FieldMetadata(keyword="CY_DOT_Y", units="km**2/s", format_spec=" .15e"),
                ]

                cy_dot_z: Annotated[
                    float,
                    Field(description="Covariance matrix [5,3]. [km**2/s]"),
                    FieldMetadata(keyword="CY_DOT_Z", units="km**2/s", format_spec=" .15e"),
                ]

                cy_dot_x_dot: Annotated[
                    float,
                    Field(description="Covariance matrix [5,4]. [km**2/s**2]"),
                    FieldMetadata(keyword="CY_DOT_X_DOT", units="km**2/s**2", format_spec=" .15e"),
                ]

                cy_dot_y_dot: Annotated[
                    float,
                    Field(description="Covariance matrix [5,5]. [km**2/s**2]"),
                    FieldMetadata(keyword="CY_DOT_Y_DOT", units="km**2/s**2", format_spec=" .15e"),
                ]

                # Row 6
                cz_dot_x: Annotated[
                    float,
                    Field(description="Covariance matrix [6,1]. [km**2/s]"),
                    FieldMetadata(keyword="CZ_DOT_X", units="km**2/s", format_spec=" .15e"),
                ]

                cz_dot_y: Annotated[
                    float,
                    Field(description="Covariance matrix [6,2]. [km**2/s]"),
                    FieldMetadata(keyword="CZ_DOT_Y", units="km**2/s", format_spec=" .15e"),
                ]

                cz_dot_z: Annotated[
                    float,
                    Field(description="Covariance matrix [6,3]. [km**2/s]"),
                    FieldMetadata(keyword="CZ_DOT_Z", units="km**2/s", format_spec=" .15e"),
                ]

                cz_dot_x_dot: Annotated[
                    float,
                    Field(description="Covariance matrix [6,4]. [km**2/s**2]"),
                    FieldMetadata(keyword="CZ_DOT_X_DOT", units="km**2/s**2", format_spec=" .15e"),
                ]

                cz_dot_y_dot: Annotated[
                    float,
                    Field(description="Covariance matrix [6,5]. [km**2/s**2]"),
                    FieldMetadata(keyword="CZ_DOT_Y_DOT", units="km**2/s**2", format_spec=" .15e"),
                ]

                cz_dot_z_dot: Annotated[
                    float,
                    Field(description="Covariance matrix [6,6]. [km**2/s**2]"),
                    FieldMetadata(keyword="CZ_DOT_Z_DOT", units="km**2/s**2", format_spec=" .15e"),
                ]

                @field_validator("epoch")
                @classmethod
                def validate_epoch(cls, v: str) -> str:
                    """Validate epoch as a CCSDS absolute date."""
                    return _validate_ccsds_date(v, "epoch")

            _delineation: ClassVar[Delineation] = Delineation("COVARIANCE_START", "COVARIANCE_STOP")
            
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments (allowed at the beginning of the OEM covariance block "
                        "only; must not appear between matrix lines, per §7.8.9). "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None

            covariance_matrix_lines: Annotated[
                list["OEM.Segment.CovarianceMatrix.CovarianceMatrixLines"],
                Field(
                    min_length=1,
                    description=(
                        "Ordered list of covariance matrix lines (increasing epoch). "
                        "One per navigation solution is recommended (5.2.5.6)."
                    ),
                ),
            ]

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            @model_validator(mode="after")
            def check_epochs_ordered(self) -> "OEM.Segment.CovarianceMatrix":
                epochs: list[str] = [m.epoch for m in self.covariance_matrix_lines]
                for i, (prev_epoch, curr_epoch) in enumerate(zip(epochs, epochs[1:]), start=1):
                    if _epoch_sort_key(curr_epoch) <= _epoch_sort_key(prev_epoch):
                        raise ValueError(
                            f"Covariance matrix epochs must be strictly increasing "
                            f"(5.2.5.7). Found epoch[{i}]='{curr_epoch}' <= "
                            f"epoch[{i-1}]='{prev_epoch}'."
                        )
                return self

            # ------------------------------------------------------------------
            # Computation shortcuts — one-line delegates, zero logic.
            # Removing these methods leaves CovarianceMatrix fully functional.
            # ------------------------------------------------------------------

            def to_numpy(self) -> Any:
                """Convert to an (N, 6, 6) numpy array of covariance matrices via NumpyBackend.

                Returns:
                    ndarray: float64 ndarray of shape (N, 6, 6).

                Raises:
                    ImportError: If numpy is not installed. Install with
                        ``pip install orbit-data-messages[numpy]``.
                """
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().covariance_to_array(self)

            @classmethod
            def from_numpy(
                cls,
                arr: Any,
                epochs: list[str],
                cov_ref_frame: str | None = None,
            ) -> "OEM.Segment.CovarianceMatrix":
                """Construct a validated CovarianceMatrix from a numpy array and epoch strings.

                Args:
                    arr (Any): float64 ndarray of shape (N, 6, 6).
                    epochs (list[str]): N CCSDS §7.5.10 epoch strings.
                    cov_ref_frame (str | None): Optional reference frame string. When
                        ``None``, no COV_REF_FRAME is set on the resulting lines.

                Returns:
                    OEM.Segment.CovarianceMatrix: A fully validated CovarianceMatrix instance.

                Raises:
                    ImportError: If numpy is not installed. Install with
                        ``pip install orbit-data-messages[numpy]``.
                """
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().covariance_from_array(arr, epochs, cov_ref_frame)

        # Segment fields
        metadata: Metadata
        ephemeris_data: EphemerisData
        covariance_matrix: CovarianceMatrix | None = Field(
            default=None,
            description=(
                "Optional covariance matrix block following the ephemeris data. "
                "Delimited by COVARIANCE_START / COVARIANCE_STOP in KVN (5.2.5)."
            ),
        )
 
        @model_validator(mode="after")
        def check_ephemeris_within_time_span(self) -> "OEM.Segment":
            """Validate all ephemeris epochs lie within [start_time, stop_time].

            §7.5.10 allows calendar and DOY formats; _epoch_sort_key normalizes both.
            """
            start: str = _epoch_sort_key(self.metadata.start_time)
            stop: str = _epoch_sort_key(self.metadata.stop_time)
            for i, sv in enumerate(self.ephemeris_data.ephemeris_data_lines):
                key: str = _epoch_sort_key(sv.epoch)
                if key < start or key > stop:
                    raise ValueError(
                        f"Ephemeris data line epoch[{i}]='{sv.epoch}' lies outside the "
                        f"declared span [{self.metadata.start_time}, {self.metadata.stop_time}]."
                    )
            return self

        @model_validator(mode="after")
        def check_covariance_within_time_span(self) -> "OEM.Segment":
            if self.covariance_matrix is None:
                return self
            start: str = _epoch_sort_key(self.metadata.start_time)
            stop: str = _epoch_sort_key(self.metadata.stop_time)
            for i, cm in enumerate(self.covariance_matrix.covariance_matrix_lines):
                key: str = _epoch_sort_key(cm.epoch)
                if key < start or key > stop:
                    raise ValueError(
                        f"Covariance matrix epoch[{i}]='{cm.epoch}' lies outside the "
                        f"declared span [{self.metadata.start_time}, {self.metadata.stop_time}]."
                    )
            return self
            

    header: Header
    segments: Annotated[
        list[Segment],
        Field(
            min_length=1,
            description=(
                "Non-empty list of (Metadata + EphemerisData + optional "
                "CovarianceMatrix) segments. At least one segment is required "
                "(table 5-1). Interpolation across consecutive segment boundaries "
                "is explicitly prohibited (5.2.4.6)."
            ),
        ),
    ]

    @model_validator(mode="after")
    def check_time_system_fixed(self) -> "OEM":
        """TIME_SYSTEM must remain fixed across all segments (5.2.4.5)."""
        systems: list[TimeSystem] = [seg.metadata.time_system for seg in self.segments]
        if len(set(systems)) > 1:
            distinct: str = ", ".join(str(s) for s in dict.fromkeys(systems))
            raise ValueError(
                f"TIME_SYSTEM must remain fixed across all segments (5.2.4.5). "
                f"Found: {distinct}."
            )
        return self
 
    @model_validator(mode="after")
    def check_useable_intervals_non_overlapping(self) -> "OEM":
        """Validate useable intervals across consecutive segments do not overlap.

        A shared endpoint is permitted (5.2.4.4). Only checked when both
        consecutive segments define useable bounds.
        """
        for i, (prev_seg, curr_seg) in enumerate(zip(self.segments, self.segments[1:]), start=1):
            prev: OEM.Segment.Metadata = prev_seg.metadata
            curr: OEM.Segment.Metadata = curr_seg.metadata
            if prev.useable_stop_time is not None and curr.useable_start_time is not None:
                if _epoch_sort_key(curr.useable_start_time) < _epoch_sort_key(prev.useable_stop_time):
                    raise ValueError(
                        f"Useable intervals of consecutive segments must not overlap "
                        f"(5.2.4.4). Segment {i-1} useable stop='{prev.useable_stop_time}' > "
                        f"segment {i} useable start='{curr.useable_start_time}'."
                    )
        return self
 
 
OrbitEphemerisMessage = OEM
