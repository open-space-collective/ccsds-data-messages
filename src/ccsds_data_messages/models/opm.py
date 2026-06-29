# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Annotated
from typing import ClassVar
from typing import Any

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from ._aliases import CCSDSDate
from ._aliases import Comment
from ._aliases import NegativeMass
from ._aliases import OptionalCCSDSDate
from ._aliases import VersionStr
from .message import CCSDS_MODEL_CONFIG
from .message import CCSDSDataMessage
from ._base import BaseCovarianceMatrix
from ._base import BaseHeader
from ._base import BaseMetadata
from ._base import BaseSpacecraftParameters
from ._fields import FieldMetadata
from .values import CenterName
from .values import ManCovRefFrame
from .values import RefFrame
from .values import TimeSystem

# Bodies for which a standard gravitational parameter is published by IAU/JPL and
# therefore GM need not appear in the message.
_KNOWN_GM_CENTERS: frozenset[CenterName] = frozenset(
    {
        CenterName.SUN,
        CenterName.MERCURY,
        CenterName.VENUS,
        CenterName.EARTH,
        CenterName.MOON,
        CenterName.MARS,
        CenterName.JUPITER,
        CenterName.SATURN,
        CenterName.URANUS,
        CenterName.NEPTUNE,
        CenterName.PLUTO,
    }
)


class OPM(CCSDSDataMessage, BaseModel):
    """
    Orbit Parameter Message (OPM).

    Provides an orbital state at a given epoch as Cartesian state vector and/or
    Keplerian elements, along with optional spacecraft parameters and maneuver data.
    Used when the recipient needs a single-epoch state rather than an ephemeris
    time series. The recipient is responsible for orbit propagation.
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "opm"

    class Header(BaseHeader):
        """
        OPM header block.

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID.
        The shared fields and their validators are inherited from BaseHeader.
        """

        ccsds_opm_vers: Annotated[
            VersionStr,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(
                keyword="CCSDS_OPM_VERS",
                order=0,
            ),
        ]

    class Metadata(BaseMetadata):
        """
        OPM metadata block.

        Describes the object, reference frame, and time system.
        The shared fields and their validators are inherited from BaseMetadata.
        OPM KVN is entirely flat: no META_START/META_STOP.
        """

        # The spec explicitly says "there is no CCSDS-based restriction on the value
        # for this keyword" and calls the YYYY-NNNP{PP} format a recommendation.
        @field_validator("ref_frame")
        @classmethod
        def validate_ref_frame_not_teme(cls, v: RefFrame | str) -> RefFrame | str:
            if v == RefFrame.TEME:
                raise ValueError("TEME is not a valid REF_FRAME for OPM (3.2.3.3).")
            return v

    class Data(BaseModel):
        """
        OPM data section.

        Contains the mandatory Cartesian state vector plus optional osculating Keplerian
        elements, spacecraft parameters, covariance matrix, maneuver parameters, and
        user-defined parameters.
        """

        model_config = CCSDS_MODEL_CONFIG

        _xml_tag: ClassVar[str] = "data"

        class StateVector(BaseModel):
            """
            Cartesian state vector at a single epoch.

            Mandatory in every OPM. Provides position (km) and velocity (km/s)
            in the reference frame declared in the metadata.
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "stateVector"

            comment: Comment = None

            epoch: Annotated[
                CCSDSDate,
                Field(
                    description="Epoch of state vector and optional Keplerian elements. (7.5.10).",
                ),
                FieldMetadata(
                    keyword="EPOCH",
                ),
            ]

            x: Annotated[
                float,
                Field(
                    description=("Position vector X-component. [km]"),
                ),
                FieldMetadata(
                    keyword="X",
                    units="km",
                    format_spec=" .3f",
                ),
            ]

            y: Annotated[
                float,
                Field(
                    description=("Position vector Y-component. [km]"),
                ),
                FieldMetadata(
                    keyword="Y",
                    units="km",
                    format_spec=" .3f",
                ),
            ]

            z: Annotated[
                float,
                Field(
                    description=("Position vector Z-component. [km]"),
                ),
                FieldMetadata(
                    keyword="Z",
                    units="km",
                    format_spec=" .3f",
                ),
            ]

            x_dot: Annotated[
                float,
                Field(
                    description=("Velocity vector X-component. [km/s]"),
                ),
                FieldMetadata(
                    keyword="X_DOT",
                    units="km/s",
                    format_spec=" .6f",
                ),
            ]

            y_dot: Annotated[
                float,
                Field(
                    description=("Velocity vector Y-component. [km/s]"),
                ),
                FieldMetadata(
                    keyword="Y_DOT",
                    units="km/s",
                    format_spec=" .6f",
                ),
            ]

            z_dot: Annotated[
                float,
                Field(
                    description=("Velocity vector Z-component. [km/s]"),
                ),
                FieldMetadata(
                    keyword="Z_DOT",
                    units="km/s",
                    format_spec=" .6f",
                ),
            ]

        class OsculatingKeplerianElements(BaseModel):
            """
            All-or-nothing osculating Keplerian elements block.

            If present on Data, all fields are required. Exactly one of true_anomaly
            or mean_anomaly must be provided.
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "keplerianElements"

            comment: Comment = None

            semi_major_axis: Annotated[
                float,
                Field(
                    description=("Semi-major axis. [km]"),
                ),
                FieldMetadata(
                    keyword="SEMI_MAJOR_AXIS",
                    units="km",
                ),
            ]

            eccentricity: Annotated[
                float,
                Field(
                    description=("Eccentricity. [dimensionless]"),
                ),
                FieldMetadata(
                    keyword="ECCENTRICITY",
                ),
            ]

            inclination: Annotated[
                float,
                Field(
                    description=("Inclination. [deg]"),
                ),
                FieldMetadata(
                    keyword="INCLINATION",
                    units="deg",
                ),
            ]

            ra_of_asc_node: Annotated[
                float,
                Field(
                    description=("Right ascension of ascending node. [deg]"),
                ),
                FieldMetadata(
                    keyword="RA_OF_ASC_NODE",
                    units="deg",
                ),
            ]

            arg_of_pericenter: Annotated[
                float,
                Field(
                    description=("Argument of pericenter. [deg]"),
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
                float | None,
                Field(
                    default=None,
                    description=(
                        "Gravitational coefficient (G times central mass). [km**3/s**2] "
                        "May be omitted when CENTER_NAME is a body whose GM is universally "
                        "published (e.g. EARTH). "
                        "Required for non-standard or user-defined orbit centers."
                    ),
                ),
                FieldMetadata(
                    keyword="GM",
                    units="km**3/s**2",
                ),
            ] = None

            @model_validator(mode="after")
            def validate_anomaly_exclusive(self) -> OPM.Data.OsculatingKeplerianElements:
                has_true: bool = self.true_anomaly is not None
                has_mean: bool = self.mean_anomaly is not None
                if has_true == has_mean:
                    raise ValueError(
                        "Exactly one of true_anomaly or mean_anomaly must be provided."
                    )
                return self

        class SpacecraftParameters(BaseSpacecraftParameters):
            """
            Shared with OMM; see models/common/spacecraft.py for the full definition.

            Mass is conditionally mandatory when maneuvers are present;
            enforced in Data.validate_maneuver_requires_mass.
            """

        class CovarianceMatrix(BaseCovarianceMatrix):
            """
            Shared with OMM; see models/common/covariance.py for the full definition.

            All-or-nothing block: if this model is present, all lower-triangular
            elements are required. COV_REF_FRAME must match the metadata REF_FRAME.
            """

        class ManeuverParameters(BaseModel):
            """
            Repeatable maneuver parameter set; all fields are optional.

            If any maneuver is present, SpacecraftParameters.mass must be provided;
            enforced in Data.validate_maneuver_requires_mass.
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "maneuverParameters"

            comment: Comment = None

            man_epoch_ignition: Annotated[
                OptionalCCSDSDate,
                Field(
                    default=None,
                    description="Epoch of ignition. (7.5.10).",
                ),
                FieldMetadata(
                    keyword="MAN_EPOCH_IGNITION",
                    block_start=True,
                ),
            ] = None

            man_duration: Annotated[
                float | None,
                Field(
                    default=None,
                    ge=0,
                    description=(
                        "Maneuver duration. [s] "
                        "Set to 0 for an impulsive maneuver."
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_DURATION",
                    units="s",
                ),
            ] = None

            man_delta_mass: Annotated[
                NegativeMass,
                Field(
                    default=None,
                    description="Mass change during maneuver. [kg] Must be negative.",
                ),
                FieldMetadata(
                    keyword="MAN_DELTA_MASS",
                    units="kg",
                ),
            ] = None

            man_ref_frame: Annotated[
                ManCovRefFrame | RefFrame | str | None,
                Field(
                    default=None,
                    description=(
                        "Reference frame for the velocity increment vector. "
                        "RSW, RTN, TNW are the preferred set; "
                        "inertial frames (e.g. EME2000, GCRF) are also used in practice. "
                        "Non-standard values are accepted as plain strings (3.2.4.11)."
                    ),
                ),
                FieldMetadata(
                    keyword="MAN_REF_FRAME",
                ),
            ] = None

            man_dv_1: Annotated[
                float | None,
                Field(
                    default=None,
                    description=("1st component of the velocity increment. [km/s]"),
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
                    description=("2nd component of the velocity increment. [km/s]"),
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
                    description=("3rd component of the velocity increment. [km/s]"),
                ),
                FieldMetadata(
                    keyword="MAN_DV_3",
                    units="km/s",
                ),
            ] = None

            @model_validator(mode="after")
            def warn_non_normative_ref_frame(self) -> OPM.Data.ManeuverParameters:
                import warnings

                _normative = {f.value for f in ManCovRefFrame}
                if self.man_ref_frame is not None and str(self.man_ref_frame) not in _normative:
                    warnings.warn(
                        f"MAN_REF_FRAME {self.man_ref_frame!r} is outside the normative "
                        "set {RSW, RTN, TNW}. This value is accepted "
                        "in practice but may not be supported by all implementations.",
                        UserWarning,
                        stacklevel=2,
                    )
                return self

        class UserDefinedParameters(BaseModel):
            """
            User-defined parameters keyed by the suffix of USER_DEFINED_x.

            All parameters must be described in an ICD (3.2.4.12).
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "userDefinedParameters"

            user_defined: dict[str, str] = Field(
                default_factory=dict,
                description=(
                    "User-defined parameters keyed by the suffix of USER_DEFINED_x. "
                    "All parameters must be described in an ICD (3.2.4.12,)."
                ),
            )

            @model_validator(mode="after")
            def validate_user_defined_not_empty(self) -> OPM.Data.UserDefinedParameters:
                if not self.user_defined:
                    raise ValueError(
                        "UserDefinedParameters block must contain at least one entry. "
                        "Omit the block entirely if no user-defined parameters are needed."
                    )
                return self

        state_vector: StateVector

        osculating_keplerian_elements: OsculatingKeplerianElements | None = Field(
            default=None,
            description=(
                "Osculating Keplerian elements. All-or-nothing block: "
                "either omit entirely or provide all parameters."
            ),
        )

        spacecraft_parameters: SpacecraftParameters | None = Field(
            default=None,
            description=(
                "Spacecraft parameters. mass is mandatory if any maneuver "
                "is defined."
            ),
        )

        covariance_matrix: CovarianceMatrix | None = Field(
            default=None,
            description=(
                "Position/velocity covariance matrix, 6 by 6 lower triangular form. "
                "All-or-nothing block."
            ),
        )

        maneuvers: list[ManeuverParameters] | None = Field(
            default=None,
            description=(
                "Maneuver parameter sets. Repeatable; if any are present, "
                "spacecraft_parameters.mass must be provided."
            ),
        )

        user_defined: UserDefinedParameters | None = Field(
            default=None,
            description=(
                "User-defined parameters. Repeatable; if any are present, "
                "all parameters must be described in an ICD."
            ),
        )

        @model_validator(mode="after")
        def validate_maneuver_requires_mass(self) -> OPM.Data:
            if not self.maneuvers:
                return self
            mass_provided: bool = (
                self.spacecraft_parameters is not None
                and self.spacecraft_parameters.mass is not None
            )
            if not mass_provided:
                raise ValueError(
                    "spacecraft_parameters.mass is required when any maneuver "
                    "is defined."
                )
            return self

    header: Header
    metadata: Metadata
    data: Data

    @model_validator(mode="after")
    def validate_gm_required(self) -> OPM:
        kep = self.data.osculating_keplerian_elements
        if kep is not None and kep.gm is None:
            if self.metadata.center_name not in _KNOWN_GM_CENTERS:
                raise ValueError(
                    f"GM is required when CENTER_NAME={self.metadata.center_name!r} "
                    "does not have a standard gravitational parameter "
                    "and GM is not provided."
                )
        return self

    @classmethod
    def builder(cls) -> OPMBuilder:
        """
        Return a builder for constructing an OPM instance.
        """
        return OPMBuilder()


class OPMBuilder:
    """Builder for OPM. Call OPM.builder() to get one."""

    def __init__(self) -> None:
        self._header_kwargs: dict = {}
        self._metadata_kwargs: dict = {}
        self._sv_kwargs: dict | None = None
        self._ke_kwargs: dict | None = None
        self._sp_kwargs: dict | None = None
        self._cov_kwargs: dict | None = None
        self._maneuvers: list[dict] = []
        self._user_defined: dict[str, str] | None = None

    def header(
        self,
        *,
        originator: str,
        creation_date: str | None = None,
        message_id: str | None = None,
        comment: list[str] | None = None,
    ) -> OPMBuilder:
        self._header_kwargs = {
            "originator": originator,
            **({"creation_date": creation_date} if creation_date is not None else {}),
            **({"message_id": message_id} if message_id is not None else {}),
            **({"comment": comment} if comment is not None else {}),
        }
        return self

    def metadata(
        self,
        *,
        object_name: str,
        object_id: str,
        center_name: CenterName,
        ref_frame: RefFrame,
        time_system: TimeSystem,
        ref_frame_epoch: str | None = None,
        comment: list[str] | None = None,
    ) -> OPMBuilder:
        self._metadata_kwargs = {
            "object_name": object_name,
            "object_id": object_id,
            "center_name": center_name,
            "ref_frame": ref_frame,
            "time_system": time_system,
            **(
                {"ref_frame_epoch": ref_frame_epoch}
                if ref_frame_epoch is not None
                else {}
            ),
            **({"comment": comment} if comment is not None else {}),
        }
        return self

    def state_vector(
        self,
        *,
        epoch: str,
        x: float,
        y: float,
        z: float,
        x_dot: float,
        y_dot: float,
        z_dot: float,
        comment: list[str] | None = None,
    ) -> OPMBuilder:
        self._sv_kwargs = {
            "epoch": epoch,
            "x": x,
            "y": y,
            "z": z,
            "x_dot": x_dot,
            "y_dot": y_dot,
            "z_dot": z_dot,
            **({"comment": comment} if comment is not None else {}),
        }
        return self

    def keplerian_elements(self, **kwargs: Any) -> OPMBuilder:
        self._ke_kwargs = kwargs
        return self

    def spacecraft_parameters(self, **kwargs: Any) -> OPMBuilder:
        self._sp_kwargs = kwargs
        return self

    def covariance_matrix(self, **kwargs: Any) -> OPMBuilder:
        self._cov_kwargs = kwargs
        return self

    def add_maneuver(self, **kwargs: Any) -> OPMBuilder:
        self._maneuvers.append(kwargs)
        return self

    def user_defined(self, **kwargs: str) -> OPMBuilder:
        self._user_defined = dict(kwargs)
        return self

    def build(self) -> OPM:
        if self._sv_kwargs is None:
            raise ValueError("state_vector() must be called before build().")
        header_kw: dict[str, Any] = dict(self._header_kwargs)
        if "creation_date" not in header_kw:
            header_kw["creation_date"] = (
                datetime.now(UTC).strftime("%Y-%jT%H:%M:%S.%f")[:-3] + "Z"
            )
        header_kw.setdefault("ccsds_opm_vers", "3.0")
        header: OPM.Header = OPM.Header(**header_kw)
        metadata: OPM.Metadata = OPM.Metadata(**self._metadata_kwargs)
        state_vector: OPM.Data.StateVector = OPM.Data.StateVector(**self._sv_kwargs)
        keplerian_elements: OPM.Data.OsculatingKeplerianElements | None = (
            OPM.Data.OsculatingKeplerianElements(**self._ke_kwargs)
            if self._ke_kwargs
            else None
        )
        spacecraft_parameters: OPM.Data.SpacecraftParameters | None = (
            OPM.Data.SpacecraftParameters(**self._sp_kwargs) if self._sp_kwargs else None
        )
        covariance_matrix: OPM.Data.CovarianceMatrix | None = (
            OPM.Data.CovarianceMatrix(**self._cov_kwargs) if self._cov_kwargs else None
        )
        maneuvers: list[OPM.Data.ManeuverParameters] | None = [
            OPM.Data.ManeuverParameters(**kwargs) for kwargs in self._maneuvers
        ] or None
        user_defined: OPM.Data.UserDefinedParameters | None = (
            OPM.Data.UserDefinedParameters(user_defined=self._user_defined)
            if self._user_defined
            else None
        )
        data: OPM.Data = OPM.Data(
            state_vector=state_vector,
            osculating_keplerian_elements=keplerian_elements,
            spacecraft_parameters=spacecraft_parameters,
            covariance_matrix=covariance_matrix,
            maneuvers=maneuvers,
            user_defined=user_defined,
        )
        return OPM(header=header, metadata=metadata, data=data)
