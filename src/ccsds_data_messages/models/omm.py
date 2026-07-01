# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from ._aliases import CCSDSDate, Comment, OMMVersionStr
from ._base import (
    BaseCovarianceMatrix,
    BaseHeader,
    BaseMetadata,
    BaseSpacecraftParameters,
)
from ._fields import FieldMetadata
from ._validators import _validate_un_oosa_designator
from .message import CCSDS_MODEL_CONFIG, CCSDSDataMessage
from .values import CenterName, MeanElementTheory, RefFrame, TimeSystem

# Frames whose epoch is intrinsic to the frame definition.
# TEME is included here because for OMMs it is always "TEME of Date"
# (epoch-intrinsic by convention per 4.2.4.9), so ref_frame_epoch is
# not required for it.


# SGP and SGP4 theories require TLE-related data blocks (4.2.4.6).
_MEAN_ELEMENT_THEORY_REQUIRING_TLE: frozenset[MeanElementTheory] = frozenset(
    {
        MeanElementTheory.SGP,
        MeanElementTheory.SGP4,
    }
)


class OMM(CCSDSDataMessage, BaseModel):
    """
    Orbit Mean-Elements Message (OMM).

    Orbit information may be exchanged between two participants by sending an orbital
    state based on mean Keplerian elements for a specified epoch using an OMM. The
    message recipient must use appropriate orbit propagator algorithms to correctly
    propagate the OMM state to compute the orbit at other desired epochs.

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

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "omm"

    class Header(BaseHeader):
        """
        OMM header block.

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID.
        The shared fields and their validators are inherited from BaseHeader.
        """

        ccsds_omm_vers: Annotated[
            OMMVersionStr,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OMM_VERS", order=0),
        ]

    class Metadata(BaseMetadata):
        """
        OMM metadata block.

        Describes the object, reference frame, time system, and mean element theory.
        The shared fields and their validators are inherited from BaseMetadata.
        OMM KVN is entirely flat: no META_START/META_STOP (section 7.4.1, table 4-2).
        """

        mean_element_theory: Annotated[
            MeanElementTheory | str,
            Field(
                description=(
                    "Description of the Mean Element Theory. Indicates the proper "
                    "method to employ to propagate the state. "
                    "Table 4-2 lists examples: SGP, SGP4, SGP4-XP, DSST, USM, PPT3; "
                    "non-standard theories are accepted as plain strings."
                ),
            ),
            FieldMetadata(keyword="MEAN_ELEMENT_THEORY"),
        ]

        # NORAD Two Line Element Sets and corresponding Simplified General
        # Perturbations (SGP) orbit propagator ephemeris outputs are explicitly
        # defined to be in the True Equator Mean Equinox of Date (TEME of Date)
        # reference frame. Therefore, TEME of date shall be used for OMMs based
        # on NORAD TLE sets, rather than the almost imperceptibly different TEME
        # of Epoch.
        @model_validator(mode="after")
        def validate_teme_constraints(self) -> OMM.Metadata:
            """
            Enforce TEME and EARTH and TEME and UTC pairings.

            TLE-based OMMs in Earth orbit must use ``CENTER_NAME=EARTH``,
            ``REF_FRAME=TEME``, and ``TIME_SYSTEM=UTC``.

            Returns:
                OMM.Metadata: The validated metadata instance.

            Raises:
                ValueError: If ``REF_FRAME=TEME`` is combined with a non-EARTH
                    center name or a non-UTC time system.
            """
            if self.ref_frame == RefFrame.TEME:
                if self.center_name != CenterName.EARTH:
                    raise ValueError(
                        "REF_FRAME=TEME is only valid for Earth-centered OMMs."
                    )
                if self.time_system != TimeSystem.UTC:
                    raise ValueError("TIME_SYSTEM must be UTC for TEME-based OMMs.")
            return self

        @model_validator(mode="after")
        def validate_tle_theory_requires_teme(self) -> OMM.Metadata:
            """§4.2.4.6: SGP/SGP4 theories require REF_FRAME=TEME, CENTER_NAME=EARTH, TIME_SYSTEM=UTC, and a UN OOSA designator-format OBJECT_ID."""
            if self.mean_element_theory in _MEAN_ELEMENT_THEORY_REQUIRING_TLE:
                if self.ref_frame != RefFrame.TEME:
                    raise ValueError(
                        f"MEAN_ELEMENT_THEORY={self.mean_element_theory} requires REF_FRAME=TEME "
                        f"(§4.2.4.6); got REF_FRAME={self.ref_frame}."
                    )
                if self.center_name != CenterName.EARTH:
                    raise ValueError(
                        f"MEAN_ELEMENT_THEORY={self.mean_element_theory} requires CENTER_NAME=EARTH "
                        f"(§4.2.4.6); got CENTER_NAME={self.center_name}."
                    )
                if self.time_system != TimeSystem.UTC:
                    raise ValueError(
                        f"MEAN_ELEMENT_THEORY={self.mean_element_theory} requires TIME_SYSTEM=UTC "
                        f"(§4.2.4.6); got TIME_SYSTEM={self.time_system}."
                    )
                _validate_un_oosa_designator(self.object_id)
            return self

    class Data(BaseModel):
        """
        OMM data section.

        Contains the mean Keplerian elements, optional spacecraft parameters,
        TLE-related parameters, covariance matrix, and user-defined parameters.
        """

        model_config = CCSDS_MODEL_CONFIG

        _xml_tag: ClassVar[str] = "data"

        class MeanKeplerianElements(BaseModel):
            """
            Exactly one of ``semi_major_axis`` or ``mean_motion`` must be provided.

            ``mean_motion`` is required (and ``semi_major_axis`` is forbidden) when
            ``mean_element_theory`` is ``SGP`` or ``SGP4``; cross-block check is
            enforced in ``Data.check_motion_vs_theory``.
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "meanElements"

            comment: Comment = None

            epoch: Annotated[
                CCSDSDate,
                Field(description="Epoch of Mean Keplerian elements."),
                FieldMetadata(keyword="EPOCH"),
            ]

            semi_major_axis: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Semi-major axis. [km] "
                        "Preferred over mean_motion except when "
                        "MEAN_ELEMENT_THEORY=SGP or SGP4, where ``mean_motion`` must be used."
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
                        "Required when ``MEAN_ELEMENT_THEORY=SGP`` or ``SGP4``; "
                        "mutually exclusive with ``semi_major_axis``."
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
                        "Gravitational coefficient (G times central mass,). [km**3/s**2] "
                        "Optional; omit when inferable from center_name."
                    ),
                ),
                FieldMetadata(
                    keyword="GM",
                    units="km**3/s**2",
                ),
            ] = None

            @model_validator(mode="after")
            def validate_motion_exclusive(self) -> OMM.Data.MeanKeplerianElements:
                has_sma: bool = self.semi_major_axis is not None
                has_mm: bool = self.mean_motion is not None
                if has_sma == has_mm:
                    raise ValueError(
                        "Exactly one of ``semi_major_axis`` or ``mean_motion`` must be provided."
                    )
                return self

        class SpacecraftParameters(BaseSpacecraftParameters):
            """Shared with OPM; see ``models/common/spacecraft.py`` for the full definition."""

        class TLERelatedParameters(BaseModel):
            """
            Required when ``MEAN_ELEMENT_THEORY=SGP`` or ``SGP4``.

            Exactly one of ``bstar`` or ``bterm`` must be provided, matching the theory:
              - ``SGP4``  -> ``bstar`` (drag parameter)
              - ``SGP4-XP`` -> ``bterm`` (ballistic coefficient CDA/m)
            ``mean_motion_dot`` is required for ``SGP`` and ``PPT3``.
            ``mean_motion_ddot`` / ``agom`` are conditional on the theory.
            Cross-block enforcement of which fields are required given
            ``mean_element_theory`` lives in ``Data.check_tle_block_constraints``.
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "tleParameters"

            comment: Comment = None

            ephemeris_type: Annotated[
                int | None,
                Field(
                    default=None,
                    description=(
                        "Ephemeris type. Default value = 0. "
                        "Common values: 0=SGP, 2=SGP4, 3=PPT3, 4=SGP4-XP, "
                        "6=Special Perturbations."
                    ),
                ),
                FieldMetadata(keyword="EPHEMERIS_TYPE", spec_default=0),
            ] = None

            classification_type: Annotated[
                str | None,
                Field(
                    default=None,
                    description=(
                        "Classification type. Default value = 'U'. "
                        "Common values: U=unclassified, S=secret."
                    ),
                ),
                FieldMetadata(keyword="CLASSIFICATION_TYPE", spec_default="U"),
            ] = None

            norad_cat_id: Annotated[
                int | None,
                Field(
                    default=None,
                    le=999_999_999,
                    description=(
                        "NORAD Catalog Number ('Satellite Number'). "
                        "An integer of up to nine digits. "
                        "Required when ``MEAN_ELEMENT_THEORY=SGP`` or ``SGP4``."
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
                        "(``MEAN_ELEMENT_THEORY=SGP`` or ``SGP4``)."
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
                        "Drag parameter for ``SGP4``. [1/Earth radii] "
                        "Required when MEAN_ELEMENT_THEORY=SGP4. "
                        "Mutually exclusive with bterm."
                    ),
                ),
                FieldMetadata(
                    keyword="BSTAR",
                    units="1/[Earth radii]",
                ),
            ] = None

            bterm: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Ballistic coefficient CDA/m for ``SGP4-XP``. [m**2/kg] "
                        "Required when MEAN_ELEMENT_THEORY=SGP4-XP. "
                        "Mutually exclusive with bstar."
                    ),
                ),
                FieldMetadata(
                    keyword="BTERM",
                    units="m**2/kg",
                ),
            ] = None

            mean_motion_dot: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "First time derivative of mean motion (drag term,). [rev/day**2] "
                        "Required when ``MEAN_ELEMENT_THEORY=SGP`` or ``PPT3``. "
                        "NOTE: if derived from a TLE, divide the TLE value by 2."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_MOTION_DOT",
                    units="rev/day**2",
                ),
            ] = None

            mean_motion_ddot: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Second time derivative of mean motion (drag term,). [rev/day**3] "
                        "Used when ``MEAN_ELEMENT_THEORY=SGP`` or ``PPT3``. "
                        "Mutually exclusive with agom. "
                        "NOTE: if derived from a TLE, divide the TLE value by 6."
                    ),
                ),
                FieldMetadata(
                    keyword="MEAN_MOTION_DDOT",
                    units="rev/day**3",
                ),
            ] = None

            agom: Annotated[
                float | None,
                Field(
                    default=None,
                    description=(
                        "Solar radiation pressure coefficient for ``SGP4-XP``. [m**2/kg] "
                        "Used when MEAN_ELEMENT_THEORY=SGP4-XP. "
                        "Mutually exclusive with ``mean_motion_ddot``."
                    ),
                ),
                FieldMetadata(
                    keyword="AGOM",
                    units="m**2/kg",
                ),
            ] = None

            @model_validator(mode="after")
            def validate_bstar_bterm_exclusive(self) -> OMM.Data.TLERelatedParameters:
                has_bstar: bool = self.bstar is not None
                has_bterm: bool = self.bterm is not None
                if has_bstar and has_bterm:
                    raise ValueError(
                        "``bstar`` and ``bterm`` are mutually exclusive. "
                        "Use bstar for SGP4 and bterm for SGP4-XP."
                    )
                return self

            @model_validator(mode="after")
            def validate_ddot_agom_exclusive(self) -> OMM.Data.TLERelatedParameters:
                has_ddot: bool = self.mean_motion_ddot is not None
                has_agom: bool = self.agom is not None
                if has_ddot and has_agom:
                    raise ValueError(
                        "``mean_motion_ddot`` and ``agom`` are mutually exclusive. "
                        "Use mean_motion_ddot for SGP/PPT3 and agom for SGP4-XP."
                    )
                return self

        class CovarianceMatrix(BaseCovarianceMatrix):
            """Shared with OPM; see ``models/common/covariance.py`` for the full definition."""

        class UserDefinedParameters(BaseModel):
            """
            User-defined parameters keyed by the suffix of USER_DEFINED_x.

            All parameters must be described in an ICD.
            """

            model_config = CCSDS_MODEL_CONFIG

            _xml_tag: ClassVar[str] = "userDefinedParameters"

            user_defined: dict[str, str] = Field(
                default_factory=dict,
                description=(
                    "User-defined parameters keyed by the suffix of USER_DEFINED_x. "
                    "All parameters must be described in an ICD."
                ),
            )

            @model_validator(mode="after")
            def validate_user_defined_not_empty(self) -> OMM.Data.UserDefinedParameters:
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
                "TLE-related parameters. Required when MEAN_ELEMENT_THEORY=SGP or SGP4."
            ),
        )

        covariance_matrix: CovarianceMatrix | None = Field(
            default=None,
            description=(
                "Position/velocity covariance matrix, 6×6 lower triangular form. "
                "All-or-nothing block."
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
    def validate_tle_block_required(self) -> OMM:
        """
        Validate that the TLE block is present for SGP/SGP4 theories.

        Returns:
            OMM: The validated OMM instance.

        Raises:
            ValueError: If ``mean_element_theory`` is ``SGP`` or ``SGP4`` but
                `tle_related_parameters` is absent.
        """
        theory: MeanElementTheory | str = self.metadata.mean_element_theory
        has_tle_block: bool = self.data.tle_related_parameters is not None

        if theory in _MEAN_ELEMENT_THEORY_REQUIRING_TLE and not has_tle_block:
            raise ValueError(
                f"tle_related_parameters block is required when "
                f"mean_element_theory='{theory}'."
            )
        return self

    @model_validator(mode="after")
    def validate_norad_cat_id_required(self) -> OMM:
        """
        Validate that ``NORAD_CAT_ID`` is provided for SGP/SGP4 theories.

        Returns:
            OMM: The validated OMM instance.

        Raises:
            ValueError: If ``mean_element_theory`` is ``SGP`` or ``SGP4`` and
                ``norad_cat_id`` is absent from ``tle_related_parameters``.
        """
        if (
            theory := self.metadata.mean_element_theory
        ) in _MEAN_ELEMENT_THEORY_REQUIRING_TLE:
            tle: OMM.Data.TLERelatedParameters | None = self.data.tle_related_parameters
            if tle is None or tle.norad_cat_id is None:
                raise ValueError(
                    "tle_related_parameters.norad_cat_id is required when "
                    f"mean_element_theory='{theory}'."
                )
        return self

    @model_validator(mode="after")
    def validate_mean_motion_required_for_tle(self) -> OMM:
        """
        Validate that ``MEAN_MOTION`` (not ``SEMI_MAJOR_AXIS``) is used for SGP/SGP4.

        Returns:
            OMM: The validated OMM instance.

        Raises:
            ValueError: If ``mean_element_theory`` is ``SGP`` or ``SGP4`` and
                ``mean_motion`` is absent from ``mean_keplerian_elements``.
        """
        theory: MeanElementTheory | str = self.metadata.mean_element_theory
        mke: OMM.Data.MeanKeplerianElements = self.data.mean_keplerian_elements
        if theory in _MEAN_ELEMENT_THEORY_REQUIRING_TLE and mke.mean_motion is None:
            raise ValueError(
                f"mean_keplerian_elements.mean_motion must be used (not semi_major_axis) "
                f"when mean_element_theory='{theory}'."
            )
        return self

    @model_validator(mode="after")
    def validate_tle_drag_params(self) -> OMM:
        """
        Enforce theory-specific drag parameter requirements in the TLE block.

        Returns:
            OMM: The validated OMM instance.

        Raises:
            ValueError: If the theory-required drag parameter (``bstar`` for SGP4,
                ``bterm``/``agom`` for SGP4-XP, ``mean_motion_dot``/
                `mean_motion_ddot` for SGP) is absent.
        """
        theory: MeanElementTheory | str = self.metadata.mean_element_theory
        if (tle := self.data.tle_related_parameters) is None:
            if theory == MeanElementTheory.SGP4_XP:
                # Table 4-3: BTERM/AGOM are Conditional ("required for SGP4 and
                # SGP4-XP mean element models") and have no home outside this
                # block, even though the block's own section heading is only
                # unconditionally mandatory for SGP/SGP4.
                raise ValueError(
                    "tle_related_parameters (with bterm and agom) is required when "
                    "mean_element_theory='SGP4-XP'."
                )
            return self

        if theory == MeanElementTheory.SGP4 and tle.bstar is None:
            raise ValueError(
                "tle_related_parameters.bstar is required when "
                "mean_element_theory='SGP4'."
            )
        if theory == MeanElementTheory.SGP4_XP:
            if tle.bterm is None:
                raise ValueError(
                    "tle_related_parameters.bterm is required when "
                    "mean_element_theory='SGP4-XP'."
                )
            if tle.agom is None:
                raise ValueError(
                    "tle_related_parameters.agom is required when "
                    "mean_element_theory='SGP4-XP'."
                )
        if theory == MeanElementTheory.SGP:
            if tle.mean_motion_dot is None:
                raise ValueError(
                    "tle_related_parameters.mean_motion_dot is required when "
                    "mean_element_theory='SGP'."
                )
            if tle.mean_motion_ddot is None:
                raise ValueError(
                    "tle_related_parameters.mean_motion_ddot is required when "
                    "mean_element_theory='SGP'."
                )
        # PPT3 is handled by check_ppt3_params, which also covers the tle-is-None case.
        return self

    @model_validator(mode="after")
    def validate_teme_requires_tle_theory(self) -> OMM:
        """
        Validate that ``TEME`` is only used with SGP/SGP4 theories.

        Returns:
            OMM: The validated OMM instance.

        Raises:
            ValueError: If ``ref_frame`` is ``TEME`` but ``mean_element_theory``
                is not ``SGP`` or ``SGP4``.
        """
        theory: MeanElementTheory | str = self.metadata.mean_element_theory
        if (
            self.metadata.ref_frame == RefFrame.TEME
            and isinstance(theory, MeanElementTheory)
            and theory not in _MEAN_ELEMENT_THEORY_REQUIRING_TLE
        ):
            raise ValueError(
                "REF_FRAME=TEME may only be used for OMMs based on NORAD TLE sets "
                "(MEAN_ELEMENT_THEORY must be SGP or SGP4)."
            )
        return self

    @model_validator(mode="after")
    def validate_ppt3_params(self) -> OMM:
        """
        Validate that PPT3 theory provides both ``MEAN_MOTION_DOT`` and ``_DDOT``.

        Returns:
            OMM: The validated OMM instance.

        Raises:
            ValueError: If ``mean_element_theory`` is ``PPT3`` and
                ``mean_motion_dot`` or ``mean_motion_ddot`` is absent.
        """
        if self.metadata.mean_element_theory == MeanElementTheory.PPT3:
            tle: OMM.Data.TLERelatedParameters | None = self.data.tle_related_parameters
            if tle is None or tle.mean_motion_dot is None:
                raise ValueError(
                    "mean_motion_dot is required when mean_element_theory='PPT3'."
                )
            if tle.mean_motion_ddot is None:
                raise ValueError(
                    "mean_motion_ddot is required when mean_element_theory='PPT3'."
                )
        return self

    header: Header
    metadata: Metadata
    data: Data

    @classmethod
    def builder(cls) -> OMMBuilder:
        """
        Return a fluent builder for constructing this message type.

        Use ``model_copy(update={...})`` to create modified copies of a frozen instance.
        """
        return OMMBuilder()


class OMMBuilder:
    """
    Fluent builder for OMM.

    Call ``header`` once, then ``metadata`` once, then ``data`` once,
    then ``build`` to validate and return a frozen ``OMM`` instance.
    """

    def __init__(self) -> None:
        self._header_kwargs: dict[str, Any] = {}
        self._metadata_kwargs: dict[str, Any] = {}
        self._mean_keplerian_elements_kwargs: dict[str, Any] = {}
        self._spacecraft_parameters_kwargs: dict[str, Any] | None = None
        self._tle_parameters_kwargs: dict[str, Any] | None = None
        self._covariance_matrix_kwargs: dict[str, Any] | None = None
        self._user_defined_kwargs: dict[str, str] | None = None

    def header(
        self,
        *,
        originator: str,
        creation_date: str | None = None,
        message_id: str | None = None,
        comment: list[str] | None = None,
    ) -> OMMBuilder:
        """
        Set header fields.

        Args:
            originator (str): Originator of the message.
            creation_date (str | None): CCSDS creation date string; defaults to the current UTC time.
            message_id (str | None): Optional message identifier.
            comment (list[str] | None): Optional list of comment strings.

        Returns:
            OMMBuilder
        """
        self._header_kwargs = {
            "ccsds_omm_vers": "3.0",
            "originator": originator,
            **({"creation_date": creation_date} if creation_date is not None else {}),
        }
        if message_id is not None:
            self._header_kwargs["message_id"] = message_id
        if comment is not None:
            self._header_kwargs["comment"] = comment
        return self

    def metadata(
        self,
        *,
        object_name: str,
        object_id: str,
        center_name: Any,
        ref_frame: Any,
        time_system: Any,
        mean_element_theory: Any,
        ref_frame_epoch: str | None = None,
        comment: list[str] | None = None,
    ) -> OMMBuilder:
        """
        Set metadata fields.

        Args:
            object_name (str): Spacecraft name.
            object_id (str): International spacecraft designator.
            center_name (Any): Origin of the reference frame (``CenterName`` enum or string).
            ref_frame (Any): Reference frame (``RefFrame`` enum).
            time_system: Time system (`TimeSystem` enum).
            mean_element_theory (Any): Mean element theory (``MeanElementTheory`` enum).
            ref_frame_epoch (str | None): Epoch of the reference frame when not intrinsic to the frame.
            comment (list[str] | None): Optional list of comment strings.

        Returns:
            OMMBuilder
        """
        self._metadata_kwargs = {
            "object_name": object_name,
            "object_id": object_id,
            "center_name": center_name,
            "ref_frame": ref_frame,
            "time_system": time_system,
            "mean_element_theory": mean_element_theory,
        }
        if ref_frame_epoch is not None:
            self._metadata_kwargs["ref_frame_epoch"] = ref_frame_epoch
        if comment is not None:
            self._metadata_kwargs["comment"] = comment
        return self

    def mean_keplerian_elements(self, **kwargs: Any) -> OMMBuilder:
        """
        Set mean Keplerian elements.

        Pass keyword arguments matching ``OMM.Data.MeanKeplerianElements`` fields.
        Exactly one of ``semi_major_axis`` or ``mean_motion`` must be provided.

        Returns:
            OMMBuilder
        """
        self._mean_keplerian_elements_kwargs = kwargs
        return self

    def spacecraft_parameters(self, **kwargs: Any) -> OMMBuilder:
        """
        Set optional spacecraft parameters.

        Pass keyword arguments matching ``OMM.Data.SpacecraftParameters`` fields.

        Returns:
            OMMBuilder
        """
        self._spacecraft_parameters_kwargs = kwargs
        return self

    def tle_parameters(self, **kwargs: Any) -> OMMBuilder:
        """
        Set optional TLE-related parameters.

        Pass keyword arguments matching ``OMM.Data.TLERelatedParameters`` fields.
        Required when ``mean_element_theory`` is ``SGP`` or ``SGP4``.

        Returns:
            OMMBuilder
        """
        self._tle_parameters_kwargs = kwargs
        return self

    def covariance_matrix(self, **kwargs: Any) -> OMMBuilder:
        """
        Set optional 6-by-6 covariance matrix.

        Pass keyword arguments matching ``OMM.Data.CovarianceMatrix`` fields.

        Returns:
            OMMBuilder
        """
        self._covariance_matrix_kwargs = kwargs
        return self

    def user_defined(self, **kwargs: str) -> OMMBuilder:
        """
        Set optional user-defined parameters.

        Pass keyword arguments whose values are strings; each becomes a
        ``USER_DEFINED_<key>`` entry. All parameters must be described in an ICD.

        Returns:
            OMMBuilder
        """
        self._user_defined_kwargs = dict(kwargs)
        return self

    def build(self) -> OMM:
        """
        Validate and return a frozen ``OMM`` instance.

        Returns:
            OMM

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        header_kw: dict[str, Any] = dict(self._header_kwargs)
        if "creation_date" not in header_kw:
            header_kw["creation_date"] = (
                datetime.now(UTC).strftime("%Y-%jT%H:%M:%S.%f")[:-3] + "Z"
            )
        header: OMM.Header = OMM.Header(**header_kw)
        metadata: OMM.Metadata = OMM.Metadata(**self._metadata_kwargs)

        spacecraft_parameters: OMM.Data.SpacecraftParameters | None = (
            OMM.Data.SpacecraftParameters(**self._spacecraft_parameters_kwargs)
            if self._spacecraft_parameters_kwargs is not None
            else None
        )
        tle_related_parameters: OMM.Data.TLERelatedParameters | None = (
            OMM.Data.TLERelatedParameters(**self._tle_parameters_kwargs)
            if self._tle_parameters_kwargs is not None
            else None
        )
        covariance_matrix: OMM.Data.CovarianceMatrix | None = (
            OMM.Data.CovarianceMatrix(**self._covariance_matrix_kwargs)
            if self._covariance_matrix_kwargs is not None
            else None
        )
        user_defined_parameters: OMM.Data.UserDefinedParameters | None = (
            OMM.Data.UserDefinedParameters(user_defined=self._user_defined_kwargs)
            if self._user_defined_kwargs is not None
            else None
        )

        data: OMM.Data = OMM.Data(
            mean_keplerian_elements=OMM.Data.MeanKeplerianElements(
                **self._mean_keplerian_elements_kwargs
            ),
            spacecraft_parameters=spacecraft_parameters,
            tle_related_parameters=tle_related_parameters,
            covariance_matrix=covariance_matrix,
            user_defined=user_defined_parameters,
        )

        return OMM(header=header, metadata=metadata, data=data)
