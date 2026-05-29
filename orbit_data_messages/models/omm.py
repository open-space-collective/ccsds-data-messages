import re
from typing import Annotated
 
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from .base import CCSDSDataMessage
from .metadata import FieldMetadata
from .values import CenterName
from .values import RefFrame
from .values import TimeSystem
from .values import ManCovRefFrame

 
_CCSDS_DATE_RE: re.Pattern[str] = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
    r"|\d{4}-\d{3}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
)
 
# Frames whose epoch is intrinsic to the frame definition.
# TEME is included here because for OMMs it is always "TEME of Date"
# (epoch-intrinsic by convention per 4.2.4.9), so ref_frame_epoch is
# not required for it.
_EPOCH_INTRINSIC_FRAMES: set[RefFrame] = {
    RefFrame.EME2000,
    RefFrame.GCRF,
    RefFrame.GRC,
    RefFrame.ICRF,
    RefFrame.ITRF2000,
    RefFrame.ITRF_93,
    RefFrame.ITRF_97,
    RefFrame.MCI,
    RefFrame.TEME,  # OMM-only; TEME of Date is the implied convention (4.2.4.9)
    # TDR and TOD remain epoch-dependent → ref_frame_epoch required.
}


_TLE_THEORIES = frozenset({"SGP", "SGP4", "SGP/SGP4"})


def _validate_ccsds_date(v: str, field_name: str) -> str:
    if not _CCSDS_DATE_RE.fullmatch(v):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DDThh:mm:ss[Z] or YYYY-DOYThh:mm:ss[Z]"
        )
    return v


class OMM(CCSDSDataMessage, BaseModel):
    """
    Orbit Mean-Elements Message (OMM).

    Orbit information may be exchanged between two participants by sending an orbital
    state based on mean Keplerian elements (see reference [H1]) for a specified epoch
    using an OMM. The message recipient must use appropriate orbit propagator algorithms
    to correctly propagate the OMM state to compute the orbit at other desired epochs.

    The OMM is intended to allow replication of the data content of an existing TLE in
    a CCSDS standard format, but the message can also accommodate other implementations
    of mean elements. All essential fields of the 'de facto standard' TLE are included
    in the OMM in a style that is consistent with that of the other ODMs (i.e., the OPM
    and OEM). From the fields in the OMM, it is possible to generate a TLE. Programs
    that convert OMMs to TLEs must be aware of the structural requirements of the TLE,
    including the checksum algorithm and the formatting requirements for the values in
    the TLE. The checksum and formatting requirements of the TLE do not apply to the
    values in an OMM.

    The use of the OMM is best applicable under the following conditions:
    - an orbit propagator consistent with the models used to develop the orbit data
      should be run at the receiver's site;
    - the receive's modeling of gravitational forces, solar radiation pressure,
      atmospheric drag, etc., should fulfill accuracy requirements established between
      the exchange partners.
    """

    class Header(BaseModel):
        """OMM header block (CCSDS 502.0-B-3 table 4-1).

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID.
        """

        ccsds_omm_vers: Annotated[
            str,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OMM_VERS"),
        ]

        # 7.8 Formatting rules
        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments allowed at the beginning of this block "
                    "per §7.8.9. See 7.8 for formatting rules."
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
                    "of this OMM. Values should be pre-coordinated between "
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

        @field_validator("ccsds_omm_vers")
        @classmethod
        def validate_version(cls, v: str) -> str:
            if not re.fullmatch(r"\d+\.\d+", v):
                raise ValueError("ccsds_omm_vers must be in 'x.y' form, e.g. '3.0'")
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
        """OMM metadata block (CCSDS 502.0-B-3 table 4-2).

        Describes the object, reference frame, time system, and mean element theory.
        Delimited by META_START / META_STOP in KVN format.
        """

        # 7.8 Formatting rules
        comment: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Comments allowed at the beginning of this block "
                    "per §7.8.9. See 7.8 for formatting rules."
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
                    "Origin of the OMM reference frame. Must be a natural solar "
                    "system body, planet barycenter, or solar system barycenter. "
                    "Select from annex B, subsection B2."
                ),
            ),
            FieldMetadata(keyword="CENTER_NAME"),
        ]

        # 3.2.3.3; accepted set of values. TEME is permitted in OMMs (4.2.4.9).
        ref_frame: Annotated[
            RefFrame,
            Field(
                description=(
                    "Reference frame for state vector and Keplerian element data. "
                    "Values outside 3.2.3.3 should be documented in an ICD. "
                    "TEME is permitted for OMMs based on NORAD TLE sets (4.2.4.9)."
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
                ),
            ),
            FieldMetadata(keyword="TIME_SYSTEM"),
        ]

        mean_element_theory: Annotated[
            str,
            Field(
                description=(
                    "Description of the Mean Element Theory. Indicates the proper "
                    "method to employ to propagate the state. "
                    "Examples: SGP, SGP4, SGP4-XP, DSST, USM."
                ),
            ),
            FieldMetadata(keyword="MEAN_ELEMENT_THEORY"),
        ]

        @field_validator("comment")
        @classmethod
        def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
            if v is not None and not v:
                raise ValueError("comment must be None or a non-empty list of strings.")
            return v

        # The spec explicitly says "there is no CCSDS-based restriction on the value
        # for this keyword" and calls the YYYY-NNNP{PP} format a recommendation.

        @field_validator("ref_frame_epoch")
        @classmethod
        def validate_ref_frame_epoch(cls, v: str | None) -> str | None:
            return _validate_ccsds_date(v, "ref_frame_epoch") if v is not None else v

        @model_validator(mode="after")
        def check_ref_frame_epoch_required(self) -> "OMM.Metadata":
            if (
                self.ref_frame not in _EPOCH_INTRINSIC_FRAMES
                and self.ref_frame_epoch is None
            ):
                raise ValueError(
                    f"ref_frame_epoch is required when ref_frame='{self.ref_frame}' "
                    f"because its epoch is not intrinsic to the frame definition."
                )
            return self

        # NORAD Two Line Element Sets and corresponding Simplified General
        # Perturbations (SGP) orbit propagator ephemeris outputs are explicitly
        # defined to be in the True Equator Mean Equinox of Date (TEME of Date)
        # reference frame. Therefore, TEME of date shall be used for OMMs based
        # on NORAD Two Line Element sets, rather than the almost imperceptibly
        # different TEME of Epoch (see reference [H2] or [H3] for further details)
        #
        # Do we need to enforce this on the model level? Check that TLERelatedParameters
        # is present and that it uses TEME?
        @model_validator(mode="after")
        def check_teme_constraints(self) -> "OMM.Metadata":
            """
            TLE-based OMMs in Earth orbit must use CENTER_NAME=EARTH,
            REF_FRAME=TEME, and TIME_SYSTEM=UTC (4.2.4.6).
            Enforce only the TEME ↔ EARTH pairing here; TIME_SYSTEM is
            a soft convention left to the application layer.
            """
            if self.ref_frame == RefFrame.TEME:
                if self.center_name != CenterName.EARTH:
                    raise ValueError(
                        "REF_FRAME=TEME is only valid for Earth-centered OMMs "
                        "(CENTER_NAME must be EARTH per 4.2.4.6)."
                    )
                if self.time_system != TimeSystem.UTC:
                    raise ValueError(
                        "TIME_SYSTEM must be UTC for TEME-based OMMs "
                        "(TIME_SYSTEM must be UTC per 4.2.4.6)."
                    )
                # The MEAN_MOTION keyword must be used instead of SEMI_MAJOR_AXIS:
                # Already enforced.
            return self

    class Data(BaseModel):
        """OMM data section (CCSDS 502.0-B-3 §4.3).

        Contains the mean Keplerian elements plus optional spacecraft parameters,
        TLE-related parameters, covariance matrix, and user-defined parameters.
        """

        class MeanKeplerianElements(BaseModel):
            """
            Exactly one of semi_major_axis or mean_motion must be provided.
            mean_motion is required (and semi_major_axis forbidden) when
            mean_element_theory is SGP or SGP4 (4.2.4.6). That cross-block
            check is enforced in Data.check_motion_vs_theory.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments allowed at the beginning of this block "
                        "per §7.8.9. See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
 
            # 7.5.10 Formatting rules
            epoch: Annotated[
                str,
                Field(
                    description=(
                        "Epoch of Mean Keplerian elements. See 7.5.10."
                    ),
                ),
                FieldMetadata(keyword="EPOCH"),
            ]
 
            semi_major_axis: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Semi-major axis. [km] "
                        "Preferred over mean_motion except when "
                        "MEAN_ELEMENT_THEORY=SGP/SGP4, where mean_motion must be used."
                    ),
                ),
                FieldMetadata(
                    keyword="SEMI_MAJOR_AXIS",
                    units="km",
                ),
            ] = None
 
            mean_motion: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Keplerian mean motion. [rev/day] "
                        "Required when MEAN_ELEMENT_THEORY=SGP/SGP4; "
                        "mutually exclusive with semi_major_axis."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_MOTION",
                    units="rev/day",
                ),
            ] = None
 
            eccentricity: Annotated[
                float,
                Field(
                    description="Eccentricity. [dimensionless]",
                ),
                FieldMetadata(keyword="ECCENTRICITY"),
            ]
 
            inclination: Annotated[
                float,
                Field(
                    description="Inclination. [deg]",
                ),
                FieldMetadata(
                    keyword="INCLINATION",
                    units="deg",
                ),
            ]
 
            ra_of_asc_node: Annotated[
                float,
                Field(
                    description="Right ascension of ascending node. [deg]",
                ),
                FieldMetadata(
                    keyword="RA_OF_ASC_NODE",
                    units="deg",
                ),
            ]
 
            arg_of_pericenter: Annotated[
                float,
                Field(
                    description="Argument of pericenter. [deg]",
                ),
                FieldMetadata(
                    keyword="ARG_OF_PERICENTER",
                    units="deg",
                ),
            ]
 
            mean_anomaly: Annotated[
                float,
                Field(
                    description=(
                        "Mean anomaly. [deg] "
                        "OMMs always use mean anomaly; true anomaly is not used."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_ANOMALY",
                    units="deg",
                ),
            ]
 
            gm: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Gravitational coefficient (G × central mass). [km**3/s**2] "
                        "Optional; omit when inferable from center_name."
                    ),
                ),
                FieldMetadata(
                    keyword="GM",
                    units="km**3/s**2", format_spec=" .1e",
                ),
            ] = None

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
 
            @model_validator(mode="after")
            def check_motion_exclusive(self) -> "OMM.Data.MeanKeplerianElements":
                has_sma = self.semi_major_axis is not None
                has_mm = self.mean_motion is not None
                if has_sma == has_mm:
                    raise ValueError(
                        "Exactly one of semi_major_axis or mean_motion must be provided."
                    )
                return self

        class SpacecraftParameters(BaseModel):
            """
            All fields are optional for OMMs (no maneuver block exists in OMM,
            so mass is never conditionally mandatory).
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments allowed at the beginning of this block "
                        "per §7.8.9. See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
            
            mass: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Spacecraft mass. [kg]"
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

        class TLERelatedParameters(BaseModel):
            """
            Required when MEAN_ELEMENT_THEORY=SGP/SGP4 (4.2.4.6).
            Exactly one of bstar or bterm must be provided, matching the theory:
              - SGP4  → bstar (drag parameter)
              - SGP4-XP → bterm (ballistic coefficient CDA/m)
            mean_motion_dot is required for SGP and PPT3.
            mean_motion_ddot / agom are conditional on the theory (4.2.4.7).
            Cross-block enforcement of which fields are required given
            mean_element_theory lives in Data.check_tle_block_constraints.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments allowed at the beginning of this block "
                        "per §7.8.9. See 7.8 for formatting rules."
                    ),
                ),
                FieldMetadata(keyword="COMMENT"),
            ] = None
 
            ephemeris_type: Annotated[
                int | None,
                Field(
                    default=None,
                    description=(
                        "Ephemeris type. Default value = 0. "
                        "Common values: 0=SGP, 2=SGP4, 3=PPT3, 4=SGP4-XP, "
                        "6=Special Perturbations. See 4.2.4.7."
                    ),
                ),
                FieldMetadata(keyword="EPHEMERIS_TYPE"),
            ] = None
 
            classification_type: Annotated[
                str | None,
                Field(
                    default=None,
                    description=(
                        "Classification type. Default value = 'U'. "
                        "Common values: U=unclassified, S=secret. See 4.2.4.7."
                    ),
                ),
                FieldMetadata(keyword="CLASSIFICATION_TYPE"),
            ] = None
 
            norad_cat_id: Annotated[
                int | None,
                Field(
                    default=None,
                    description=(
                        "NORAD Catalog Number ('Satellite Number'). "
                        "An integer of up to nine digits. "
                        "Required when MEAN_ELEMENT_THEORY=SGP/SGP4."
                    ),
                ),
                FieldMetadata(keyword="NORAD_CAT_ID"),
            ] = None
 
            element_set_no: Annotated[
                int | None,
                Field(
                    default=None,
                    description=(
                        "Element set number for this satellite. Normally incremented "
                        "sequentially. Meaningful only for TLE-based data "
                        "(MEAN_ELEMENT_THEORY=SGP/SGP4)."
                    ),
                ),
                FieldMetadata(keyword="ELEMENT_SET_NO"),
            ] = None
 
            rev_at_epoch: Annotated[
                int | None,
                Field(
                    default=None,
                    description="Revolution number at epoch.",
                ),
                FieldMetadata(keyword="REV_AT_EPOCH"),
            ] = None
 
            bstar: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Drag parameter for SGP4. [1/Earth radii] "
                        "Required when MEAN_ELEMENT_THEORY=SGP4. "
                        "Mutually exclusive with bterm."
                    ),
                ),
                FieldMetadata(
                    keyword="BSTAR",
                    units="1/[Earth radii]", format_spec=" .1e",
                ),
            ] = None
 
            bterm: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Ballistic coefficient CDA/m for SGP4-XP. [m**2/kg] "
                        "Required when MEAN_ELEMENT_THEORY=SGP4-XP. "
                        "Mutually exclusive with bstar."
                    ),
                ),
                FieldMetadata(
                    keyword="BTERM",
                    units="m**2/kg", format_spec=" .1e",
                ),
            ] = None
 
            mean_motion_dot: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "First time derivative of mean motion (drag term). [rev/day**2] "
                        "Required when MEAN_ELEMENT_THEORY=SGP or PPT3. "
                        "NOTE: if derived from a TLE, divide the TLE value by 2 (4.2.4.7)."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_MOTION_DOT",
                    units="rev/day**2", format_spec=" .1e",
                ),
            ] = None
 
            mean_motion_ddot: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Second time derivative of mean motion (drag term). [rev/day**3] "
                        "Used when MEAN_ELEMENT_THEORY=SGP or PPT3. "
                        "Mutually exclusive with agom. "
                        "NOTE: if derived from a TLE, divide the TLE value by 6 (4.2.4.7)."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_MOTION_DDOT",
                    units="rev/day**3", format_spec=" .1e",
                ),
            ] = None
 
            agom: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Solar radiation pressure coefficient for SGP4-XP. [m**2/kg] "
                        "Used when MEAN_ELEMENT_THEORY=SGP4-XP. "
                        "Mutually exclusive with mean_motion_ddot."
                    ),
                ),
                FieldMetadata(
                    keyword="AGOM",
                    units="m**2/kg", format_spec=" .1e",
                ),
            ] = None

            @field_validator("comment")
            @classmethod
            def validate_comment_not_empty(cls, v: list[str] | None) -> list[str] | None:
                if v is not None and not v:
                    raise ValueError("comment must be None or a non-empty list of strings.")
                return v
 
            @model_validator(mode="after")
            def check_bstar_bterm_exclusive(self) -> "OMM.Data.TLERelatedParameters":
                has_bstar = self.bstar is not None
                has_bterm = self.bterm is not None
                if has_bstar and has_bterm:
                    raise ValueError(
                        "bstar and bterm are mutually exclusive. "
                        "Use bstar for SGP4 and bterm for SGP4-XP."
                    )
                return self
 
            @model_validator(mode="after")
            def check_ddot_agom_exclusive(self) -> "OMM.Data.TLERelatedParameters":
                has_ddot = self.mean_motion_ddot is not None
                has_agom = self.agom is not None
                if has_ddot and has_agom:
                    raise ValueError(
                        "mean_motion_ddot and agom are mutually exclusive. "
                        "Use mean_motion_ddot for SGP/PPT3 and agom for SGP4-XP."
                    )
                return self

        class CovarianceMatrix(BaseModel):
            """
            All-or-nothing block: if this model is present on Data, all 21
            lower-triangular elements are required. COV_REF_FRAME may be
            omitted if identical to metadata REF_FRAME; that cross-block
            check is left to the OMM layer.
            """
            # 7.8 Formatting rules
            comment: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Comments allowed at the beginning of this block "
                        "per §7.8.9. See 7.8 for formatting rules."
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

        class UserDefinedParameters(BaseModel):
            """
            User-defined parameters keyed by the suffix of USER_DEFINED_x.
            All parameters must be described in an ICD (4.2.4.10).
            """
            user_defined: dict[str, str] = Field(
                default_factory=dict,
                description=(
                    "User-defined parameters keyed by the suffix of USER_DEFINED_x. "
                    "All parameters must be described in an ICD (4.2.4.10)."
                ),
            )
 
            @model_validator(mode="after")
            def check_user_defined_not_empty(self) -> "OMM.Data.UserDefinedParameters":
                if not self.user_defined:
                    raise ValueError(
                        "UserDefinedParameters block must contain at least one entry. "
                        "Omit the block entirely if no user-defined parameters are needed."
                    )
                return self

        # Data fields
        mean_keplerian_elements: MeanKeplerianElements
 
        spacecraft_parameters: SpacecraftParameters | None = Field(
            default=None,
            description="Spacecraft parameters. All fields are optional for OMMs.",
        )
 
        tle_related_parameters: TLERelatedParameters | None = Field(
            default=None,
            description=(
                "TLE-related parameters. Required when "
                "MEAN_ELEMENT_THEORY=SGP/SGP4 (4.2.4.6)."
            ),
        )
 
        covariance_matrix: CovarianceMatrix | None = Field(
            default=None,
            description=(
                "Position/velocity covariance matrix, 6×6 lower triangular form. "
                "All-or-nothing block (4.2.4.5)."
            ),
        )
 
        user_defined: UserDefinedParameters | None = Field(
            default=None,
            description=(
                "User-defined parameters. Repeatable; if any are present, "
                "all parameters must be described in an ICD (4.2.4.10)."
            ),
        )

        # OMM-level cross-block validators
 
    @model_validator(mode="after")
    def check_tle_block_required(self) -> "OMM":
        """
        When MEAN_ELEMENT_THEORY is SGP or SGP4, the TLE-related parameters
        block must be present and NORAD_CAT_ID must be provided (4.2.4.6).
        """
        theory = self.metadata.mean_element_theory.upper()
        has_tle_block = self.data.tle_related_parameters is not None
 
        if theory in _TLE_THEORIES and not has_tle_block:
            raise ValueError(
                f"tle_related_parameters block is required when "
                f"mean_element_theory='{theory}' (4.2.4.6)."
            )
        return self
 
    @model_validator(mode="after")
    def check_norad_cat_id_required(self) -> "OMM":
        """NORAD_CAT_ID is required when MEAN_ELEMENT_THEORY=SGP/SGP4 (4.2.4.6)."""
        theory = self.metadata.mean_element_theory.upper()
        if theory in _TLE_THEORIES:
            tle = self.data.tle_related_parameters
            if tle is None or tle.norad_cat_id is None:
                raise ValueError(
                    "tle_related_parameters.norad_cat_id is required when "
                    f"mean_element_theory='{theory}' (4.2.4.6)."
                )
        return self
 
    @model_validator(mode="after")
    def check_mean_motion_required_for_tle(self) -> "OMM":
        """
        When MEAN_ELEMENT_THEORY=SGP/SGP4, MEAN_MOTION must be used instead
        of SEMI_MAJOR_AXIS (4.2.4.6).
        """
        theory = self.metadata.mean_element_theory.upper()
        mke = self.data.mean_keplerian_elements
        if theory in _TLE_THEORIES and mke.mean_motion is None:
            raise ValueError(
                f"mean_keplerian_elements.mean_motion must be used (not semi_major_axis) "
                f"when mean_element_theory='{theory}' (4.2.4.6)."
            )
        return self
 
    @model_validator(mode="after")
    def check_tle_drag_params(self) -> "OMM":
        """
        Enforce theory-specific drag parameter requirements within the TLE block.
        """
        theory = self.metadata.mean_element_theory.upper()
        tle = self.data.tle_related_parameters
        if tle is None:
            return self
 
        if theory == "SGP4":
            if tle.bstar is None:
                raise ValueError(
                    "tle_related_parameters.bstar is required when "
                    "mean_element_theory='SGP4' (4.2.4.7)."
                )
        if theory == "SGP4-XP":
            if tle.bterm is None:
                raise ValueError(
                    "tle_related_parameters.bterm is required when "
                    "mean_element_theory='SGP4-XP' (4.2.4.7)."
                )
            if tle.agom is None:
                raise ValueError(
                    "tle_related_parameters.agom is required when "
                    "mean_element_theory='SGP4-XP' (4.2.4.7)."
                )
        if theory == "SGP/SGP4":
            if tle.bstar is None:
                raise ValueError("bstar is required when mean_element_theory='SGP/SGP4'")
            if tle.mean_motion_dot is None:
                raise ValueError("mean_motion_dot is required when mean_element_theory='SGP/SGP4'")
            if tle.mean_motion_ddot is None:
                raise ValueError("mean_motion_ddot is required when mean_element_theory='SGP/SGP4'")
        if theory == "SGP":
            if tle.mean_motion_dot is None:
                raise ValueError("mean_motion_dot is required when mean_element_theory='SGP'")
            if tle.mean_motion_ddot is None:
                raise ValueError("mean_motion_ddot is required when mean_element_theory='SGP'")
        # PPT3 is handled by check_ppt3_params, which also covers the tle-is-None case.
        return self

    @model_validator(mode="after")
    def check_teme_requires_tle_theory(self) -> "OMM":
        if self.metadata.ref_frame == RefFrame.TEME:
            if self.metadata.mean_element_theory.upper() not in _TLE_THEORIES:
                raise ValueError(
                    "REF_FRAME=TEME may only be used for OMMs based on NORAD TLE sets "
                    "(MEAN_ELEMENT_THEORY must be SGP, SGP4, or SGP/SGP4 per 4.2.4.9)."
                )
        return self

    @model_validator(mode="after")
    def check_ppt3_params(self) -> "OMM":
        if self.metadata.mean_element_theory.upper() == "PPT3":
            tle = self.data.tle_related_parameters
            if tle is None or tle.mean_motion_dot is None:
                raise ValueError(
                    "mean_motion_dot is required when mean_element_theory='PPT3' (table 4-3)."
                )
            if tle.mean_motion_ddot is None:
                raise ValueError(
                    "mean_motion_ddot is required when mean_element_theory='PPT3' (table 4-3)."
                )
        return self


    header: Header
    metadata: Metadata
    data: Data


OrbitMeanElementsMessage = OMM
