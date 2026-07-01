# SPDX-License-Identifier: Apache-2.0

"""
Shared base classes for CCSDS data message blocks.

Consolidates the common building blocks used across CCSDS data messages:

``BaseHeader``
    Fields shared by all CCSDS data message types. Subclasses declare their
    spec-matching version field first, then inherit these fields.

``BaseMetadata`` / ``_validate_ref_frame_epoch``
    Metadata fields shared by OPM and OMM. The module-level validator
    ``_validate_ref_frame_epoch`` is extracted so that OEM.Segment.Metadata
    (which cannot inherit BaseMetadata) can reuse the same logic.

``BaseCovarianceMatrix``
    Lower-triangular 6 by 6 position/velocity covariance matrix shared by
    OPM and OMM. OEM uses a structurally different inline covariance block.

``BaseSpacecraftParameters``
    Optional spacecraft physical parameter fields shared by OPM and OMM.
"""

from __future__ import annotations

from typing import Annotated, ClassVar

from pydantic import BaseModel, Field, model_validator

from ._aliases import Comment, CreationDate, OptionalCCSDSDate
from ._fields import FieldMetadata
from .message import CCSDS_MODEL_CONFIG
from .values import CenterName, ManCovRefFrame, Organization, RefFrame, TimeSystem

# Reference frames for which the REF_FRAME_EPOCH metadata keyword is not required
# per the CCSDS specification.
#
# "Epoch-intrinsic" means the frame's reference epoch is either hardcoded directly
# into its name/definition, or it matches the data state epoch by convention:
#   - TEME: "True Equator Mean Equinox of Date," evaluated at the state epoch.
#   - TOD:  "True of Date," the equator and equinox match the state epoch,
#           obviating the need for a separate epoch pointer (per IERS conventions).
#   - TDR:  "True of Date, Rotating," follows the same "of date" temporal
#           semantics as TOD.
#   - ITRF realizations (1993, 1997, 2000): The geodetic measurement epoch is built
#     directly into the realization name (e.g. ITRF1997, ITRF2000).
#   - MCI:  Mars-Centric Inertial, a single-body inertial frame whose pole
#           orientation is defined by the IAU planetary model, not an external epoch.
#   - B1950: Besselian epoch 1950.0 is hardcoded into the frame's definition.
#   - J2000: Julian epoch J2000.0 (JD 2451545.0 TDB) is hardcoded into the frame's
#            definition.
#   - WGS84: Earth-fixed geodetic datum; same "realization name carries the epoch"
#            reasoning as the ITRF entries above.
#
# NOTE on OPM: The Orbit Parameter Message (OPM) parser rejects TEME via a field
# validator before this set is evaluated; its inclusion here ensures complete
# compliance across other ODM types (e.g., OMM).
#
# NOTE on GRC: Greenwich Rotation Coordinate is excluded because it rotates with
# Greenwich Apparent Sidereal Time and depends on Earth Orientation Parameters (EOP).
# It requires a REF_FRAME_EPOCH to lock the specific EOP table realization.
#
# NOTE on TEMEOFEPOCH: excluded, not included by oversight. Per the SANA registry,
# TEMEOFEPOCH is "Earth's TEMEOfDate frame evaluated at some specified epoch" - i.e.
# it requires an externally-supplied REF_FRAME_EPOCH to say *which* epoch, the
# opposite of epoch-intrinsic.
_EPOCH_INTRINSIC_FRAMES: frozenset[RefFrame] = frozenset(
    {
        RefFrame.B1950,
        RefFrame.EME2000,
        RefFrame.GCRF,
        RefFrame.ICRF,
        RefFrame.ITRF1997,
        RefFrame.ITRF2000,
        RefFrame.ITRF_93,
        RefFrame.ITRF_97,
        RefFrame.J2000,
        RefFrame.MCI,
        RefFrame.TDR,
        RefFrame.TEME,
        RefFrame.TOD,
        RefFrame.WGS84,
    }
)


def _validate_ref_frame_epoch(
    ref_frame: RefFrame | str | None,
    ref_frame_epoch: OptionalCCSDSDate,
) -> None:
    """
    Assert that REF_FRAME_EPOCH is present whenever the frame is not epoch-intrinsic.

    Extracted as a standalone function so that both ``BaseMetadata`` and
    ``OEM.Segment.Metadata`` (which cannot inherit ``BaseMetadata``) share the same
    logic without drift.

    Args:
        ref_frame (RefFrame | str | None): The REF_FRAME value from the metadata block.
        ref_frame_epoch (OptionalCCSDSDate): The REF_FRAME_EPOCH value, or None if absent.

    Raises:
        ValueError: If ``ref_frame`` is not in ``_EPOCH_INTRINSIC_FRAMES`` and
            ``ref_frame_epoch`` is ``None``.
    """
    if ref_frame not in _EPOCH_INTRINSIC_FRAMES and ref_frame_epoch is None:
        raise ValueError(
            f"ref_frame_epoch is required when ref_frame={ref_frame!r} "
            "because its epoch is not intrinsic to the frame definition."
        )


class BaseHeader(BaseModel):
    """
    Shared header fields for all CCSDS data message types (version field excluded).

    Subclasses declare their spec-matching version field first, then inherit these fields
    and their validators. The KVN writer handles the resulting model_fields ordering so
    the version keyword is always emitted first in the output KVN file.
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "header"

    comment: Comment = None

    classification: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "User-defined free-text message classification or caveats. "
                "Values should be pre-coordinated between exchanging entities."
            ),
        ),
        FieldMetadata(keyword="CLASSIFICATION"),
    ] = None

    creation_date: CreationDate

    originator: Annotated[
        Organization | str,
        Field(
            description=(
                "Creating agency or operator. "
                "Select from the SANA Registry of Organizations (Annex B1, "
                "https://sanaregistry.org/r/organizations): use the Abbreviation "
                "column value when present, or the Name column when no abbreviation "
                "is listed. Non-standard values are accepted as plain strings."
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


class BaseMetadata(BaseModel):
    """
    Shared metadata fields for OPM and OMM.

    Both message types describe the same object identification, reference frame, and
    time system fields with identical types and validation rules. Subclasses add their
    message-specific fields and TEME-handling validators.
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "metadata"

    comment: Comment = None

    object_name: Annotated[
        str,
        Field(
            description=(
                "Spacecraft name. There is no CCSDS-based restriction on this value; "
                "recommended to use names from the UN Office of Outer Space Affairs "
                "designator index. Set to 'UNKNOWN' if unavailable or undisclosed."
            ),
        ),
        FieldMetadata(keyword="OBJECT_NAME"),
    ]

    object_id: Annotated[
        str,
        Field(
            description=(
                "International spacecraft designator. There is no CCSDS-based restriction "
                "on this value; recommended format is YYYY-NNNP{PP} per the UN OOSA "
                "designator index. For assets not in the UNOOSA index, non-standard "
                "identifiers are valid. Set to 'UNKNOWN' if unavailable or undisclosed."
            ),
        ),
        FieldMetadata(keyword="OBJECT_ID"),
    ]

    center_name: Annotated[
        CenterName | str,
        Field(
            description=(
                "Origin of the reference frame. Typically a natural solar "
                "system body, planet barycenter, or solar system barycenter. "
                "Select from the SANA Registry of Orbit Centers (Annex B2, "
                "https://sanaregistry.org/r/orbit_centers): use the Name column value. "
                "Non-standard bodies are accepted as plain strings."
            ),
        ),
        FieldMetadata(keyword="CENTER_NAME"),
    ]

    ref_frame: Annotated[
        RefFrame | str,
        Field(
            description=(
                "Reference frame for state vector and Keplerian element data. "
                "The SANA Registry of Celestial Body Reference Frames (Annex B4, "
                "https://sanaregistry.org/r/celestial_body_reference_frames) "
                "lists the standard set; values outside that set are valid when "
                "documented in an ICD. Parametric frames (e.g. ITRF2014, ICRF3) "
                "are supported via RefFrame.parametric()."
            ),
        ),
        FieldMetadata(keyword="REF_FRAME"),
    ]

    ref_frame_epoch: Annotated[
        OptionalCCSDSDate,
        Field(
            default=None,
            description=(
                "Epoch of the reference frame. Mandatory when the epoch is not "
                "intrinsic to the frame definition. CCSDS date/time format (7.5.10, Annex A)."
            ),
        ),
        FieldMetadata(keyword="REF_FRAME_EPOCH"),
    ] = None

    time_system: Annotated[
        TimeSystem | str,
        Field(
            description=(
                "Time system for state vector and covariance data. "
                "The SANA Registry of Time Systems (Annex B3, "
                "https://sanaregistry.org/r/time_systems) lists the standard set; "
                "values outside that set are valid when documented in an ICD. "
                "If MET or MRT, the mission/event epoch should appear in a comment or ICD. "
                "Timestamps should use three-digit day-of-duration format (7.5.10, Annex A), "
                "not calendar date format."
            ),
        ),
        FieldMetadata(keyword="TIME_SYSTEM"),
    ]

    @model_validator(mode="after")
    def validate_ref_frame_epoch_required(self) -> BaseMetadata:
        _validate_ref_frame_epoch(self.ref_frame, self.ref_frame_epoch)
        return self


class BaseCovarianceMatrix(BaseModel):
    """
    6 by 6 lower-triangular position/velocity covariance matrix.

    All-or-nothing block: if this model is present, all 21 lower-triangular elements
    are required. COV_REF_FRAME may be omitted when it equals the metadata REF_FRAME;
    that cross-block check is left to the enclosing data message model.

    Units: km**2 (position/position), km**2/s (position/velocity),
    km**2/s**2 (velocity/velocity). Values should be expressed in standard double
    precision (7.5, Annex A).
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "covarianceMatrix"

    comment: Comment = None

    cov_ref_frame: Annotated[
        ManCovRefFrame | RefFrame | str | None,
        Field(
            default=None,
            description=(
                "Reference frame for covariance data. "
                "The SANA Registry of Orbit-Relative Reference Frames (Annex B5, "
                "https://sanaregistry.org/r/orbit_relative_reference_frames) "
                "lists the standard set; values outside that set are valid when "
                "documented in an ICD. Parametric frames (e.g. ITRF2014, ICRF3) "
                "are supported via RefFrame.parametric(). "
                "Inertial frames (e.g. TEME, GCRF) are also accepted in practice. "
                "Non-standard values are accepted as plain strings. "
                "May be omitted if identical to the metadata REF_FRAME."
            ),
        ),
        FieldMetadata(keyword="COV_REF_FRAME"),
    ] = None

    # The spec imposes no validity constraint beyond numeric format.
    # A zero variance (e.g., cx_x = 0.0) is valid per the spec. A positive-definiteness
    # check would add a mathematical constraint the spec does not mandate.

    # Row 1
    cx_x: Annotated[
        float,
        Field(
            description="Covariance matrix [1,1]. [km**2]",
        ),
        FieldMetadata(
            keyword="CX_X",
            units="km**2",
            format_spec=" .15e",
        ),
    ]

    # Row 2
    cy_x: Annotated[
        float,
        Field(
            description="Covariance matrix [2,1]. [km**2]",
        ),
        FieldMetadata(
            keyword="CY_X",
            units="km**2",
            format_spec=" .15e",
        ),
    ]

    cy_y: Annotated[
        float,
        Field(
            description="Covariance matrix [2,2]. [km**2]",
        ),
        FieldMetadata(
            keyword="CY_Y",
            units="km**2",
            format_spec=" .15e",
        ),
    ]

    # Row 3
    cz_x: Annotated[
        float,
        Field(
            description="Covariance matrix [3,1]. [km**2]",
        ),
        FieldMetadata(
            keyword="CZ_X",
            units="km**2",
            format_spec=" .15e",
        ),
    ]

    cz_y: Annotated[
        float,
        Field(
            description="Covariance matrix [3,2]. [km**2]",
        ),
        FieldMetadata(
            keyword="CZ_Y",
            units="km**2",
            format_spec=" .15e",
        ),
    ]

    cz_z: Annotated[
        float,
        Field(
            description="Covariance matrix [3,3]. [km**2]",
        ),
        FieldMetadata(
            keyword="CZ_Z",
            units="km**2",
            format_spec=" .15e",
        ),
    ]

    # Row 4
    cx_dot_x: Annotated[
        float,
        Field(
            description="Covariance matrix [4,1]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CX_DOT_X",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cx_dot_y: Annotated[
        float,
        Field(
            description="Covariance matrix [4,2]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CX_DOT_Y",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cx_dot_z: Annotated[
        float,
        Field(
            description="Covariance matrix [4,3]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CX_DOT_Z",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cx_dot_x_dot: Annotated[
        float,
        Field(
            description="Covariance matrix [4,4]. [km**2/s**2]",
        ),
        FieldMetadata(
            keyword="CX_DOT_X_DOT",
            units="km**2/s**2",
            format_spec=" .15e",
        ),
    ]

    # Row 5
    cy_dot_x: Annotated[
        float,
        Field(
            description="Covariance matrix [5,1]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CY_DOT_X",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cy_dot_y: Annotated[
        float,
        Field(
            description="Covariance matrix [5,2]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CY_DOT_Y",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cy_dot_z: Annotated[
        float,
        Field(
            description="Covariance matrix [5,3]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CY_DOT_Z",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cy_dot_x_dot: Annotated[
        float,
        Field(
            description="Covariance matrix [5,4]. [km**2/s**2]",
        ),
        FieldMetadata(
            keyword="CY_DOT_X_DOT",
            units="km**2/s**2",
            format_spec=" .15e",
        ),
    ]

    cy_dot_y_dot: Annotated[
        float,
        Field(
            description="Covariance matrix [5,5]. [km**2/s**2]",
        ),
        FieldMetadata(
            keyword="CY_DOT_Y_DOT",
            units="km**2/s**2",
            format_spec=" .15e",
        ),
    ]

    # Row 6
    cz_dot_x: Annotated[
        float,
        Field(
            description="Covariance matrix [6,1]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CZ_DOT_X",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cz_dot_y: Annotated[
        float,
        Field(
            description="Covariance matrix [6,2]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CZ_DOT_Y",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cz_dot_z: Annotated[
        float,
        Field(
            description="Covariance matrix [6,3]. [km**2/s]",
        ),
        FieldMetadata(
            keyword="CZ_DOT_Z",
            units="km**2/s",
            format_spec=" .15e",
        ),
    ]

    cz_dot_x_dot: Annotated[
        float,
        Field(
            description="Covariance matrix [6,4]. [km**2/s**2]",
        ),
        FieldMetadata(
            keyword="CZ_DOT_X_DOT",
            units="km**2/s**2",
            format_spec=" .15e",
        ),
    ]

    cz_dot_y_dot: Annotated[
        float,
        Field(
            description="Covariance matrix [6,5]. [km**2/s**2]",
        ),
        FieldMetadata(
            keyword="CZ_DOT_Y_DOT",
            units="km**2/s**2",
            format_spec=" .15e",
        ),
    ]

    cz_dot_z_dot: Annotated[
        float,
        Field(
            description="Covariance matrix [6,6]. [km**2/s**2]",
        ),
        FieldMetadata(
            keyword="CZ_DOT_Z_DOT",
            units="km**2/s**2",
            format_spec=" .15e",
        ),
    ]


class BaseSpacecraftParameters(BaseModel):
    """
    Spacecraft physical parameters block.

    All fields are optional. In OPM, mass is conditionally mandatory when
    maneuver parameters are present; that cross-block constraint is enforced
    at the data message level, not here.
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "spacecraftParameters"

    comment: Comment = None

    mass: Annotated[
        float | None,
        Field(
            default=None,
            description="Spacecraft mass. [kg]",
        ),
        FieldMetadata(
            keyword="MASS",
            units="kg",
        ),
    ] = None

    solar_rad_area: Annotated[
        float | None,
        Field(
            default=None, ge=0, description="Solar radiation pressure area (AR) [m**2]."
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
            description="Solar radiation pressure coefficient (CR) [dimensionless]. "
            "If 0, no solar radiation pressure shall be considered.",
        ),
        FieldMetadata(keyword="SOLAR_RAD_COEFF"),
    ] = None

    drag_area: Annotated[
        float | None,
        Field(
            default=None,
            ge=0,
            description="Drag area (AD) [m**2].",
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
                "Drag coefficient (CD) [dimensionless]. "
                "If 0, no atmospheric drag shall be considered."
            ),
        ),
        FieldMetadata(keyword="DRAG_COEFF"),
    ] = None
