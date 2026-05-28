import re
from datetime import datetime as _datetime
from datetime import timedelta as _timedelta
from typing import Annotated
from typing import Any

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator
from pydantic import PrivateAttr
 
from .base import CCSDSDataMessage
from .metadata import Delineation
from .metadata import FieldMetadata
from .values import CenterName
from .values import RefFrame
from .values import TimeSystem
from .values import ManCovRefFrame

 
_CCSDS_DATE_RE: re.Pattern[str] = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
    r"|\d{4}-\d{3}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
)
 
# Frames whose epoch is intrinsic to the frame definition (shared with OPM/OMM).
# OEM allows TEME in REF_FRAME (same latitude as OMM; not explicitly forbidden).
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

 
def _epoch_sort_key(epoch: str) -> str:
    """
    Return a lexicographically sortable calendar-format string for a CCSDS
    epoch, converting day-of-year format to calendar format when necessary.

    §7.5.10 allows two epoch formats:
      YYYY-MM-DDThh:mm:ss[.d][Z]  (calendar)
      YYYY-DOYThh:mm:ss[.d][Z]    (day-of-year, 3-digit day)

    Both formats sort correctly by string comparison when used consistently.
    Mixed sequences would produce incorrect comparisons, so DOY epochs are
    normalised to calendar format before comparison.
    """
    e = epoch.rstrip("Z")
    # DOY format detected by: year(4) dash doy(3) 'T' — position 8 is 'T'.
    if len(e) > 8 and e[4] == "-" and e[8] == "T" and e[5:8].isdigit():
        year = int(e[:4])
        doy  = int(e[5:8])
        date = (_datetime(year, 1, 1) + _timedelta(days=doy - 1)).strftime("%Y-%m-%d")
        return date + "T" + e[9:]
    return e


def _validate_ccsds_date(v: str, field_name: str) -> str:
    if not _CCSDS_DATE_RE.fullmatch(v):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DDThh:mm:ss[.d+][Z] or "
            f"YYYY-DOYThh:mm:ss[.d+][Z]"
        )
    return v


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
                    "Comments (allowed in the OPM Header "
                    "only immediately after the OPM version number). "
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
            if v is not None and len(v) == 0:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        @field_validator("creation_date")
        @classmethod
        def validate_creation_date(cls, v: str) -> str:
            return _validate_ccsds_date(v, "creation_date")

    class Segment(BaseModel):
        """
        One (Metadata + EphemerisData + optional CovarianceSection) block.
        The OEM body is a non-empty list of these segments (table 5-1).
        """

        class Metadata(BaseModel):
            """
            Per-segment metadata, delimited by META_START / META_STOP in KVN.
            Modelled here as a plain dataclass; the delimiters are a serialisation
            concern, not a domain concern.
            """
            # Private attribute: Hidden from initialization, schemas, and optionality signals
            _delineation: Delineation = PrivateAttr(
                default_factory=lambda: Delineation("META_START", "META_STOP")
            )

            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments (allowed in the OPM Header "
                        "only immediately after the OPM version number). "
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
                CenterName,
                Field(
                    description=(
                        "Origin of the OEM reference frame. May be a natural solar "
                        "system body, planet barycenter, solar system barycenter, or "
                        "another reference frame center (e.g. a spacecraft). "
                        "Natural bodies from annex B, subsection B2; spacecraft by "
                        "OBJECT_ID or UN OOSA international designator."
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
                str | None,
                Field(
                    default=None,
                    description=(
                        "Recommended interpolation method for ephemeris data "
                        "(e.g. HERMITE, LINEAR, LAGRANGE). "
                        "interpolation_degree must be provided if this is set."
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
                if v is not None and len(v) == 0:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            # The spec explicitly says "there is no CCSDS-based restriction on the value
            # for this keyword" and calls the YYYY-NNNP{PP} format a recommendation
            #
            # @field_validator("object_id")
            # @classmethod
            # def validate_object_id(cls, v: str) -> str:
            #     if v != "UNKNOWN" and not re.fullmatch(r"\d{4}-\d{3}[A-Z]+", v):
            #         raise ValueError(
            #             "object_id must be 'UNKNOWN' or match YYYY-NNNP{PP}, e.g. '2000-052A'"
            #         )
            #     return v
 
            @field_validator("ref_frame_epoch", "start_time", "stop_time",
                             "useable_start_time", "useable_stop_time",
                             mode="before")
            @classmethod
            def validate_time_fields(cls, v: str | None, info) -> str | None:
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
            def check_interpolation_degree_required(self) -> "OEM.Segment.Metadata":
                if self.interpolation is not None and self.interpolation_degree is None:
                    raise ValueError(
                        "interpolation_degree is required when interpolation is set "
                        "(table 5-3)."
                    )
                return self
 
            @model_validator(mode="after")
            def check_useable_times_within_total_span(self) -> "OEM.Segment.Metadata":
                """
                Useable start/stop must lie within [start_time, stop_time].
                §7.5.10 allows two epoch formats (calendar and DOY); _epoch_sort_key
                normalises both to calendar format before comparison.
                """
                def _key(t: str) -> str:
                    return _epoch_sort_key(t)

                if self.useable_start_time is not None:
                    if _key(self.useable_start_time) < _key(self.start_time):
                        raise ValueError(
                            "useable_start_time must not be earlier than start_time."
                        )
                    if _key(self.useable_start_time) > _key(self.stop_time):
                        raise ValueError(
                            "useable_start_time must not be later than stop_time."
                        )
                if self.useable_stop_time is not None:
                    if _key(self.useable_stop_time) > _key(self.stop_time):
                        raise ValueError(
                            "useable_stop_time must not be later than stop_time."
                        )
                    if _key(self.useable_stop_time) < _key(self.start_time):
                        raise ValueError(
                            "useable_stop_time must not be earlier than start_time."
                        )
                if (self.useable_start_time is not None
                    and self.useable_stop_time is not None
                    and _key(self.useable_start_time) > _key(self.useable_stop_time)):
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
            """
            The list of ephemeris data lines for one segment.
            comment is allowed only at the beginning of the ephemeris data section
            (7.8.9); it must not appear between data lines.
            ephemeris_data_lines must be non-empty and ordered by increasing epoch.
            """
            
            # Each set of ephemeris data, including the time tag, must be provided on
            # a single line. The order in which data items are given shall be fixed:
            #     Epoch, X, Y, Z, X_DOT, Y_DOT, Z_DOT, X_DDOT, Y_DDOT, Z_DDOT.
            #
            # At least one space character must be used to separate the items in each
            # ephemeris data line.
            class EphemerisDataLine(BaseModel):
                """
                One ephemeris data line: epoch + position + velocity + optional acceleration.
                Acceleration is all-or-nothing: if any component is provided, all three
                must be provided (5.2.4.1-5.2.4.2).
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
                    FieldMetadata(
                        keyword="X",
                        units="km",
                    ),
                ]
    
                y: Annotated[
                    float,
                    Field(
                        description=(
                            "Position vector Y-component. [km]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="Y",
                        units="km",
                    ),
                ]
    
                z: Annotated[
                    float,
                    Field(
                        description=(
                            "Position vector Z-component. [km]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="Z",
                        units="km",
                    ),
                ]
    
                x_dot: Annotated[
                    float,
                    Field(description=(
                        "Velocity vector X-component. [km/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="X_DOT",
                        units="km/s",
                    ),
                ]
    
                y_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Velocity vector Y-component. [km/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="Y_DOT",
                        units="km/s",
                    ),
                ]
    
                z_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Velocity vector Z-component. [km/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="Z_DOT",
                        units="km/s",
                    ),
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
                    FieldMetadata(
                        keyword="X_DDOT",
                        units="km/s**2",
                    ),
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
                    FieldMetadata(
                        keyword="Y_DDOT",
                        units="km/s**2",
                    ),
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
                    FieldMetadata(
                        keyword="Z_DDOT",
                        units="km/s**2",
                    ),
                ] = None
    
                @field_validator("epoch")
                @classmethod
                def validate_epoch(cls, v: str) -> str:
                    return _validate_ccsds_date(v, "epoch")
    
                @model_validator(mode="after")
                def check_acceleration_all_or_nothing(self) -> "OEM.Segment.EphemerisData.EphemerisDataLine":
                    components = (self.x_ddot, self.y_ddot, self.z_ddot)
                    present = [c for c in components if c is not None]
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
                        "Comments (allowed in the OPM Header "
                        "only immediately after the OPM version number). "
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
                if v is not None and len(v) == 0:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            @model_validator(mode="after")
            def check_epochs_ordered(self) -> "OEM.Segment.EphemerisData.EphemerisDataLine":
                epochs = [sv.epoch for sv in self.ephemeris_data_lines]
                for i in range(1, len(epochs)):
                    if _epoch_sort_key(epochs[i]) <= _epoch_sort_key(epochs[i - 1]):
                        raise ValueError(
                            f"Ephemeris data line epochs must be strictly increasing. "
                            f"Found epoch[{i}]='{epochs[i]}' <= epoch[{i-1}]='{epochs[i-1]}'."
                        )
                return self
 
            # @model_validator(mode="after")
            # def check_acceleration_consistency(self) -> "OEM.Segment.EphemerisData.EphemerisDataLine":
            #     """
            #     While the spec allows mixing lines with and without accelerations
            #     within a block (each line is independently valid), uniform presence
            #     is strongly expected in practice. Warn via ValueError if mixed to
            #     surface likely data errors early.
            #     """
            #     has_accel = [sv.x_ddot is not None for sv in self.ephemeris_data_lines]
            #     if any(has_accel) and not all(has_accel):
            #         raise ValueError(
            #             "Acceleration components must be present on all state vector "
            #             "lines or none within a single ephemeris block. Mixed blocks "
            #             "are not permitted."
            #         )
            #     return self

            # ------------------------------------------------------------------
            # Computation shortcuts — one-line delegates, zero logic.
            # Removing these methods leaves EphemerisData fully functional.
            # ------------------------------------------------------------------

            def to_numpy(self) -> Any:
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().to_array(self)

            def to_ostk(self) -> Any:
                from orbit_data_messages.compute.backends.ostk_ import OSTkBackend
                return OSTkBackend().trajectory_from_ephemeris(self)

            @classmethod
            def from_numpy(cls, arr: Any, epochs: list[str]) -> "OEM.Segment.EphemerisData":
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().ephemeris_data_from_array(arr, epochs)

            @classmethod
            def from_ostk(cls, trajectory: Any) -> "OEM.Segment.EphemerisData":
                from orbit_data_messages.compute.backends.ostk_ import OSTkBackend
                return OSTkBackend().ephemeris_data_from_trajectory(trajectory)

        class CovarianceMatrix(BaseModel):
            """
            The optional covariance matrix block that follows an ephemeris data block,
            delimited by COVARIANCE_START / COVARIANCE_STOP in KVN.
            Contains one or more CovarianceMatrixLines entries ordered by increasing epoch
            (5.2.5.6–5.2.5.7).
            comment is allowed only at the beginning of the section (7.8.9).
            """

            class CovarianceMatrixLines(BaseModel):
                """
                A single covariance matrix within the covariance matrix.
                Each has its own EPOCH and optional COV_REF_FRAME, followed by
                the 21 lower-triangular elements (rows 1-6, left to right).
                Units: km**2, km**2/s, km**2/s**2 per 7.7.2.2 (not displayed in data lines).
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
                    Field(
                        description=(
                            "Covariance matrix [1,1]. [km**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CX_X",
                        units="km**2",
                    ),
                ]

                # Row 2
                cy_x: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [2,1]. [km**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_X",
                        units="km**2",
                    ),
                ]

                cy_y: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [2,2]. [km**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_Y",
                        units="km**2",
                    ),
                ]

                # Row 3
                cz_x: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [3,1]. [km**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_X",
                        units="km**2",
                    ),
                ]

                cz_y: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [3,2]. [km**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_Y", 
                        units="km**2"
                    ),
                ]

                cz_z: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [3,3]. [km**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_Z",
                        units="km**2",
                    ),
                ]

                # Row 4
                cx_dot_x: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [4,1]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_X",
                        units="km**2/s",
                    ),
                ]

                cx_dot_y: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [4,2]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_Y",
                        units="km**2/s",
                    ),
                ]

                cx_dot_z: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [4,3]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_Z",
                        units="km**2/s",
                    ),
                ]

                cx_dot_x_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [4,4]. [km**2/s**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_X_DOT",
                        units="km**2/s**2",
                    ),
                ]

                # Row 5
                cy_dot_x: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [5,1]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_X",
                        units="km**2/s",
                    ),
                ]

                cy_dot_y: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [5,2]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_Y",
                        units="km**2/s",
                    ),
                ]

                cy_dot_z: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [5,3]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_Z",
                        units="km**2/s",
                    ),
                ]

                cy_dot_x_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [5,4]. [km**2/s**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_X_DOT",
                        units="km**2/s**2",
                    ),
                ]

                cy_dot_y_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [5,5]. [km**2/s**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_Y_DOT",
                        units="km**2/s**2",
                    ),
                ]

                # Row 6
                cz_dot_x: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [6,1]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_X",
                        units="km**2/s",
                    ),
                ]

                cz_dot_y: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [6,2]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Y",
                        units="km**2/s",
                    ),
                ]

                cz_dot_z: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [6,3]. [km**2/s]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Z",
                        units="km**2/s",
                    ),
                ]

                cz_dot_x_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [6,4]. [km**2/s**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_X_DOT",
                        units="km**2/s**2",
                    ),
                ]
                cz_dot_y_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [6,5]. [km**2/s**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Y_DOT",
                        units="km**2/s**2",
                    ),
                ]

                cz_dot_z_dot: Annotated[
                    float,
                    Field(
                        description=(
                            "Covariance matrix [6,6]. [km**2/s**2]"
                        ),
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Z_DOT",
                        units="km**2/s**2",
                    ),
                ]

                @field_validator("epoch")
                @classmethod
                def validate_epoch(cls, v: str) -> str:
                    return _validate_ccsds_date(v, "epoch")

                # The spec imposes no validity constraint beyond numeric format.
                # A zero variance (e.g., cx_x = 0.0) is expressible in double precision
                # and passes all stated spec requirements, yet this check rejects it.
                # The check adds a mathematical constraint that the spec does not mandate.
                #
                # @model_validator(mode="after")
                # def check_covariance_positive_definite_proxy(self) -> "OEM.Data.CovarianceMatrixLines":
                #     """
                #     Proxy check for positive-definiteness: verifies all diagonal (variance)
                #     elements are strictly positive. Necessary but not sufficient for a valid
                #     covariance matrix. A full Cholesky-based check would be sufficient but
                #     requires numpy or similar to be computationally efficient.
                #     """
                #     diagonal = [
                #         ("CX_X", self.cx_x),
                #         ("CY_Y", self.cy_y),
                #         ("CZ_Z", self.cz_z),
                #         ("CX_DOT_X_DOT", self.cx_dot_x_dot),
                #         ("CY_DOT_Y_DOT", self.cy_dot_y_dot),
                #         ("CZ_DOT_Z_DOT", self.cz_dot_z_dot),
                #     ]
                #     non_positive = [kw for kw, v in diagonal if v <= 0]
                #     if non_positive:
                #         raise ValueError(
                #             f"Covariance diagonal elements must be strictly positive "
                #             f"(variance cannot be zero or negative). "
                #             f"Failing elements: {', '.join(non_positive)}"
                #         )
                #     return self

            _delineation: Delineation = PrivateAttr(
                default_factory=lambda: Delineation("COVARIANCE_START", "COVARIANCE_STOP")
            )
            
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments (allowed in the OPM Header "
                        "only immediately after the OPM version number). "
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
                if v is not None and len(v) == 0:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v
 
            @model_validator(mode="after")
            def check_epochs_ordered(self) -> "OEM.Segment.CovarianceMatrix.CovarianceMatrixLines":
                epochs = [m.epoch for m in self.covariance_matrix_lines]
                for i in range(1, len(epochs)):
                    if _epoch_sort_key(epochs[i]) <= _epoch_sort_key(epochs[i - 1]):
                        raise ValueError(
                            f"Covariance matrix epochs must be strictly increasing "
                            f"(5.2.5.7). Found epoch[{i}]='{epochs[i]}' <= "
                            f"epoch[{i-1}]='{epochs[i-1]}'."
                        )
                return self

            # ------------------------------------------------------------------
            # Computation shortcuts — one-line delegates, zero logic.
            # Removing these methods leaves CovarianceMatrix fully functional.
            # ------------------------------------------------------------------

            def to_numpy(self) -> Any:
                from orbit_data_messages.compute.backends.numpy_ import NumpyBackend
                return NumpyBackend().covariance_to_array(self)

            @classmethod
            def from_numpy(
                cls,
                arr: Any,
                epochs: list[str],
                cov_ref_frame: str | None = None,
            ) -> "OEM.Segment.CovarianceMatrix":
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
            """
            All ephemeris data line epochs must lie within [start_time, stop_time].
            §7.5.10 allows calendar and DOY formats; _epoch_sort_key normalises both.
            """
            start = _epoch_sort_key(self.metadata.start_time)
            stop  = _epoch_sort_key(self.metadata.stop_time)
            for i, sv in enumerate(self.ephemeris_data.ephemeris_data_lines):
                key = _epoch_sort_key(sv.epoch)
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
            start = _epoch_sort_key(self.metadata.start_time)
            stop  = _epoch_sort_key(self.metadata.stop_time)
            for i, cm in enumerate(self.covariance_matrix.covariance_matrix_lines):
                key = _epoch_sort_key(cm.epoch)
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
        systems = [seg.metadata.time_system for seg in self.segments]
        if len(set(systems)) > 1:
            distinct = ", ".join(str(s) for s in dict.fromkeys(systems))
            raise ValueError(
                f"TIME_SYSTEM must remain fixed across all segments (5.2.4.5). "
                f"Found: {distinct}."
            )
        return self
 
    @model_validator(mode="after")
    def check_useable_intervals_non_overlapping(self) -> "OEM":
        """
        Useable intervals across consecutive segments must not overlap,
        except for a possibly shared endpoint (5.2.4.4).
        Only checked when both consecutive segments define useable bounds.
        """
        for i in range(1, len(self.segments)):
            prev = self.segments[i - 1].metadata
            curr = self.segments[i].metadata
            if prev.useable_stop_time is not None and curr.useable_start_time is not None:
                if _epoch_sort_key(curr.useable_start_time) < _epoch_sort_key(prev.useable_stop_time):
                    raise ValueError(
                        f"Useable intervals of consecutive segments must not overlap "
                        f"(5.2.4.4). Segment {i-1} useable stop='{prev.useable_stop_time}' > "
                        f"segment {i} useable start='{curr.useable_start_time}'."
                    )
        return self
 
 
OrbitEphemerisMessage = OEM
