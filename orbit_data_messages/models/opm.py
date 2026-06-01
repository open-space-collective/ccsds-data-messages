from __future__ import annotations

import re
from typing import Annotated
from typing import ClassVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from .base import CCSDSDataMessage
from ._epoch import _validate_ccsds_date
from .metadata import Delineation
from .metadata import FieldMetadata
from .values import CenterName
from .values import RefFrame
from .values import TimeSystem
from .values import ManCovRefFrame

_EPOCH_INTRINSIC_FRAMES: set[RefFrame] = {
    RefFrame.EME2000,
    RefFrame.GCRF,
    RefFrame.GRC,
    RefFrame.ICRF,
    RefFrame.ITRF2000,
    RefFrame.ITRF_93,
    RefFrame.ITRF_97,
    RefFrame.MCI,
    # TDR and TOD are "True of Date" frames — epoch-dependent, so ref_frame_epoch
    # is required for them.
}


class OPM(CCSDSDataMessage, BaseModel):
    """
    Orbit Parameter Message (OPM).

    Provides an orbital state at a given epoch as Cartesian state vector and/or
    Keplerian elements, along with optional spacecraft parameters and maneuver data.
    Used when the recipient needs a single-epoch state rather than an ephemeris
    time series. The recipient is responsible for orbit propagation.
    """

    class Header(BaseModel):
        """OPM header block (CCSDS 502.0-B-3 table 3-1).

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID.
        """

        ccsds_opm_vers: Annotated[
            str,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OPM_VERS"),
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
                    "of this OPM. Values should be pre-coordinated between "
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

        @field_validator("ccsds_opm_vers")
        @classmethod
        def validate_version(cls, v: str) -> str:
            if not re.fullmatch(r"\d+\.\d+", v):
                raise ValueError("ccsds_opm_vers must be in 'x.y' form, e.g. '3.0'")
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
        """OPM metadata block (CCSDS 502.0-B-3 table 3-2).

        Describes the object, reference frame, and time system.
        Delimited by META_START / META_STOP in KVN format.
        """
        _delineation: ClassVar[Delineation] = Delineation("META_START", "META_STOP")

        # 7.8 Formatting rules
        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments, allowed only at the beginning of the OPM Metadata. "
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

        # Annex B, subsection B2; accepted set of values
        center_name: Annotated[
            CenterName,
            Field(
                description=(
                    "Origin of the OPM reference frame. Must be a natural solar "
                    "system body, planet barycenter, or solar system barycenter. "
                    "Select from annex B, subsection B2."
                ),
            ),
            FieldMetadata(keyword="CENTER_NAME"),
        ]

        # 3.2.3.3; accepted set of values
        ref_frame: Annotated[
            RefFrame,
            Field(
                description=(
                    "Reference frame for state vector and Keplerian element data. "
                    "Values outside 3.2.3.3 should be documented in an ICD."
                ),
            ),
            FieldMetadata(keyword="REF_FRAME"),
        ]

        # 7.5.10 Formatting rules
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

        # 3.2.3.2; accepted set of values
        time_system: Annotated[
            TimeSystem,
            Field(
                description=(
                    "Time system for state vector, maneuver, and covariance data. "
                    "Values outside 3.2.3.2 should be documented in an ICD. "
                    "If MET or MRT, mission/event epoch must appear in a comment or ICD."
                ),
            ),
            FieldMetadata(keyword="TIME_SYSTEM"),
        ]

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        # The spec explicitly says "there is no CCSDS-based restriction on the value
        # for this keyword" and calls the YYYY-NNNP{PP} format a recommendation.

        # Should this be enforced? Specs only note is "only used in OMMs."
        @field_validator("ref_frame")
        @classmethod
        def validate_ref_frame_not_teme(cls, v: RefFrame) -> RefFrame:
            if v == RefFrame.TEME:
                raise ValueError(
                    "TEME is not a valid REF_FRAME for OPM (3.2.3.3)."
                )
            return v

        @field_validator("ref_frame_epoch")
        @classmethod
        def validate_ref_frame_epoch(cls, v: str | None) -> str | None:
            return _validate_ccsds_date(v, "ref_frame_epoch") if v is not None else v

        @model_validator(mode="after")
        def check_ref_frame_epoch_required(self) -> "OPM.Metadata":
            if (
                self.ref_frame not in _EPOCH_INTRINSIC_FRAMES
                and self.ref_frame_epoch is None
            ):
                raise ValueError(
                    f"ref_frame_epoch is required when ref_frame='{self.ref_frame}' "
                    f"because its epoch is not intrinsic to the frame definition."
                )
            return self

    class Data(BaseModel):
        """OPM data section (CCSDS 502.0-B-3 §3.3).

        Contains the mandatory Cartesian state vector plus optional osculating Keplerian
        elements, spacecraft parameters, covariance matrix, maneuver parameters, and
        user-defined parameters.
        """

        class StateVector(BaseModel):
            """Cartesian state vector at a single epoch (CCSDS 502.0-B-3 §3.3.3).

            Mandatory in every OPM. Provides position (km) and velocity (km/s)
            in the reference frame declared in the metadata.
            """

            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments, allowed only at the beginning of the OPM Metadata. "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None

            # 7.5.10 Formatting rules
            epoch: Annotated[
                str,
                Field(
                    description=(
                        "Epoch of state vector and optional Keplerian elements. See 7.5.10."
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
                Field(
                    description=(
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

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            @field_validator("epoch")
            @classmethod
            def validate_epoch(cls, v: str) -> str:
                return _validate_ccsds_date(v, "epoch")

        class OsculatingKeplerianElements(BaseModel):
            """
            All-or-nothing block: if this model is present on Data, all fields
            are required. Exactly one of true_anomaly or mean_anomaly must be
            provided.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments, allowed only at the beginning of the OPM Metadata. "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
            
            semi_major_axis: Annotated[
                float,
                Field(
                    description=(
                        "Semi-major axis. [km]"
                    ),
                ),
                FieldMetadata(
                    keyword="SEMI_MAJOR_AXIS",
                    units="km",
                ),
            ]
            
            eccentricity: Annotated[
                float,
                Field(
                    description=(
                        "Eccentricity. [dimensionless]"
                    ),
                ),
                FieldMetadata(
                    keyword="ECCENTRICITY",
                ),
            ]
            
            inclination: Annotated[
                float,
                Field(
                    description=(
                        "Inclination. [deg]"
                    ),
                ),
                FieldMetadata(
                    keyword="INCLINATION",
                    units="deg"
                ),
            ]
            
            ra_of_asc_node: Annotated[
                float,
                Field(
                    description=(
                        "Right ascension of ascending node. [deg]"
                    ),
                ),
                FieldMetadata(
                    keyword="RA_OF_ASC_NODE",
                    units="deg",
                ),
            ]
            
            arg_of_pericenter: Annotated[
                float,
                Field(
                    description=(
                        "Argument of pericenter. [deg]"
                    ),
                ),
                FieldMetadata(
                    keyword="ARG_OF_PERICENTER",
                    units="deg",
                ),
            ]
            
            true_anomaly: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "True anomaly. [deg] Mutually exclusive with mean_anomaly."
                    ),
                ),
                FieldMetadata(
                    keyword="TRUE_ANOMALY",
                    units="deg",
                ),
            ] = None
            
            mean_anomaly: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Mean anomaly. [deg] Mutually exclusive with true_anomaly."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_ANOMALY",
                    units="deg",
                ),
            ] = None
            
            gm: Annotated[
                float,
                Field(
                    description=(
                        "Gravitational coefficient (G × central mass). [km**3/s**2] "
                        "Required when not inferable from center_name."
                    ),
                ),
                FieldMetadata(
                    keyword="GM",
                    units="km**3/s**2", format_spec=" .1e",
                ),
            ]

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            @model_validator(mode="after")
            def check_anomaly_exclusive(self) -> "OPM.Data.OsculatingKeplerianElements":
                has_true: bool = self.true_anomaly is not None
                has_mean: bool = self.mean_anomaly is not None
                if has_true == has_mean:
                    raise ValueError(
                        "Exactly one of true_anomaly or mean_anomaly must be provided."
                    )
                return self

        class SpacecraftParameters(BaseModel):
            """
            mass is conditional: mandatory if any maneuver is defined (3.2.4.9).
            That cross-block condition is enforced in Data.check_maneuver_requires_mass.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments, allowed only at the beginning of the OPM Metadata. "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
            
            mass: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Spacecraft mass. [kg] "
                        "Mandatory if any maneuver is defined (3.2.4.9)."
                    ),
                ),
                FieldMetadata(
                    keyword="MASS",
                    units="kg",
                ),
            ] = None

            solar_rad_area: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Solar radiation pressure area (AR). [m**2] "
                        "If 0, no solar radiation pressure is considered (3.2.4.5)."
                    ),
                ),
                FieldMetadata(
                    keyword="SOLAR_RAD_AREA",
                    units="m**2",
                ),
            ] = None
            
            solar_rad_coeff: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Solar radiation pressure coefficient (CR). [dimensionless]"
                    ),
                ),
                FieldMetadata(keyword="SOLAR_RAD_COEFF"),
            ] = None

            drag_area: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Drag area (AD). [m**2] "
                        "If 0, no atmospheric drag is considered (3.2.4.6)."
                    ),
                ),
                FieldMetadata(
                    keyword="DRAG_AREA",
                    units="m**2",
                ),
            ] = None
                
            drag_coeff: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Drag coefficient (CD). [dimensionless]"
                    ),
                ),
                FieldMetadata(keyword="DRAG_COEFF"),
            ] = None

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

        class CovarianceMatrix(BaseModel):
            """
            All-or-nothing block: if this model is present on Data, all 21
            lower-triangular elements are required. COV_REF_FRAME may be
            omitted if identical to metadata REF_FRAME; that cross-block
            check is left to the OPM layer.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments, allowed only at the beginning of the OPM Metadata. "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
            
            cov_ref_frame: Annotated[
                ManCovRefFrame | None,
                Field(
                    default=None,
                    description=(
                        "Reference frame for covariance data (3.2.4.11). "
                        "May be omitted if identical to metadata REF_FRAME."
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
                    units="km**2", format_spec=" .15e",
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
                    units="km**2", format_spec=" .15e",
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
                    units="km**2", format_spec=" .15e",
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
                    units="km**2", format_spec=" .15e",
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
                    units="km**2", format_spec=" .15e"
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
                    units="km**2", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s**2", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s**2", format_spec=" .15e",
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
                    units="km**2/s**2", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s", format_spec=" .15e",
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
                    units="km**2/s**2", format_spec=" .15e",
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
                    units="km**2/s**2", format_spec=" .15e",
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
                    units="km**2/s**2", format_spec=" .15e",
                ),
            ]

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            # The spec imposes no validity constraint beyond numeric format.
            # A zero variance (e.g., cx_x = 0.0) is expressible in double precision
            # and passes all stated spec requirements. A positive-definiteness check
            # would add a mathematical constraint the spec does not mandate.

        class ManeuverParameters(BaseModel):
            """
            All fields are Optional per the spec. Repeatable: Data holds a
            list of these. If any maneuver is present, SpacecraftParameters.mass
            must be provided - enforced in Data.check_maneuver_requires_mass.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments, allowed only at the beginning of the OPM Metadata. "
                        "See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
            
            man_epoch_ignition: Annotated[
                str | None,
                Field(
                    default=None,
                    description=(
                        "Epoch of ignition. See 7.5.10 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="MAN_EPOCH_IGNITION"),
            ] = None

            man_duration: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Maneuver duration. [s] "
                        "Set to 0 for an impulsive maneuver (3.2.4.7)."
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_DURATION",
                    units="s",
                ),
            ] = None

            man_delta_mass: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Mass change during maneuver. [kg] "
                        "Must be negative (3.2.4.7)."
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_DELTA_MASS",
                    units="kg",
                ),
            ] = None

            man_ref_frame: Annotated[
                ManCovRefFrame | None,
                Field(
                    default=None,
                    description=(
                        "Reference frame for the velocity increment vector (3.2.4.11)."
                    ),
                ),
                FieldMetadata(keyword="MAN_REF_FRAME"),
            ] = None

            man_dv_1: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "1st component of the velocity increment. [km/s]"
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_DV_1",
                    units="km/s",
                ),
            ] = None

            man_dv_2: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "2nd component of the velocity increment. [km/s]"
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_DV_2",
                    units="km/s",
                ),
            ] = None

            man_dv_3: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "3rd component of the velocity increment. [km/s]"
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_DV_3",
                    units="km/s",
                ),
            ] = None

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v

            @field_validator("man_epoch_ignition")
            @classmethod
            def validate_man_epoch_ignition(cls, v: str | None) -> str | None:
                return _validate_ccsds_date(v, "man_epoch_ignition") if v is not None else v

            @field_validator("man_delta_mass")
            @classmethod
            def validate_man_delta_mass(cls, v: float | None) -> float | None:
                if v is not None and v >= 0:
                    raise ValueError("MAN_DELTA_MASS must be negative.")
                return v

        class UserDefinedParameters(BaseModel):
            """
            User-defined parameters keyed by the suffix of USER_DEFINED_x.
            All parameters must be described in an ICD (3.2.4.12).
            """
            user_defined: dict[str, str] = Field(
                default_factory=dict,
                description=(
                    "User-defined parameters keyed by the suffix of USER_DEFINED_x. "
                    "All parameters must be described in an ICD (3.2.4.12)."
                ),
            )

            @model_validator(mode="after")
            def check_user_defined_not_empty(self) -> "OPM.Data.UserDefinedParameters":
                if not self.user_defined:
                    raise ValueError(
                        "UserDefinedParameters block must contain at least one entry. "
                        "Omit the block entirely if no user-defined parameters are needed."
                    )
                return self

        # Data fields
        state_vector: StateVector

        osculating_keplerian_elements: OsculatingKeplerianElements | None = Field(
            default=None,
            description=(
                "Osculating Keplerian elements. All-or-nothing block: "
                "either omit entirely or provide all parameters (3.2.4.1)."
            ),
        )

        spacecraft_parameters: SpacecraftParameters | None = Field(
            default=None,
            description=(
                "Spacecraft parameters. mass is mandatory if any maneuver "
                "is defined (3.2.4.9)."
            ),
        )

        covariance_matrix: CovarianceMatrix | None = Field(
            default=None,
            description=(
                "Position/velocity covariance matrix, 6×6 lower triangular form. "
                "All-or-nothing block (3.2.4.10)."
            ),
        )

        maneuvers: list[ManeuverParameters] | None = Field(
            default=None,
            description=(
                "Maneuver parameter sets. Repeatable; if any are present, "
                "spacecraft_parameters.mass must be provided (3.2.4.9)."
            ),
        )

        user_defined: UserDefinedParameters | None = Field(
            default=None,
            description=(
                "User-defined parameters. Repeatable; if any are present, "
                "all parameters must be described in an ICD (3.2.4.12)."
            ),
        )

        @model_validator(mode="after")
        def check_maneuver_requires_mass(self) -> "OPM.Data":
            if not self.maneuvers:
                return self
            mass_provided: bool = (
                self.spacecraft_parameters is not None
                and self.spacecraft_parameters.mass is not None
            )
            if not mass_provided:
                raise ValueError(
                    "spacecraft_parameters.mass is required when any maneuver "
                    "is defined (3.2.4.9)."
                )
            return self

    header: Header
    metadata: Metadata
    data: Data


OrbitParameterMessage = OPM
