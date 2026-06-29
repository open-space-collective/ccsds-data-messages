# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import itertools
from datetime import UTC
from datetime import datetime
from typing import Annotated
from typing import Any
from typing import ClassVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from ._aliases import CCSDSDate
from ._aliases import Comment
from ._aliases import OptionalCCSDSDate
from ._aliases import VersionStr
from .message import CCSDS_MODEL_CONFIG
from .message import CCSDSDataMessage
from ._base import BaseHeader
from ._base import _validate_ref_frame_epoch
from ._epoch import _epoch_sort_key
from ._fields import Delineation
from ._fields import FieldMetadata
from .values import CenterName
from .values import Interpolation
from .values import ManCovRefFrame
from .values import RefFrame
from .values import TimeSystem


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

    Note: field order within nested classes follows CCSDS table order,
    not required-before-optional. This is intentional for spec traceability.
    """

    model_config = CCSDS_MODEL_CONFIG

    _xml_tag: ClassVar[str] = "oem"

    class Header(BaseHeader):
        """
        OEM header block (table 5-2).

        Contains the message version, optional comments and classification,
        creation date, originator, and optional message ID. The header appears
        once at the top of the file, before the first segment.
        The shared fields and their validators are inherited from BaseHeader.
        """

        ccsds_oem_vers: Annotated[
            VersionStr,
            Field(
                description=(
                    "Format version in the form of 'x.y', where "
                    "'y' is incremented for corrections and minor "
                    "changes, and 'x' is incremented for major changes."
                ),
            ),
            FieldMetadata(keyword="CCSDS_OEM_VERS"),
        ]

    class Segment(BaseModel):
        """
        One (Metadata + EphemerisData + optional CovarianceSection) block.

        The OEM body is a non-empty list of these segments (table 5-1).
        """

        model_config = CCSDS_MODEL_CONFIG

        _xml_tag: ClassVar[str] = "segment"

        class Metadata(BaseModel):
            """
            Per-segment metadata, delimited by META_START / META_STOP in KVN.

            The delimiters are a serialization concern, not a domain concern.
            """

            model_config = CCSDS_MODEL_CONFIG

            _delineation: ClassVar[Delineation] = Delineation("META_START", "META_STOP")
            _xml_tag: ClassVar[str] = "metadata"

            comment: Comment = None

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
                        "system body (select from annex B, subsection B2,) or another "
                        "reference frame center such as a spacecraft (use OBJECT_ID or "
                        "UN OOSA international designator per section 5.2.3). "
                        "Natural bodies resolve to CenterName enum members; spacecraft "
                        "IDs are accepted as plain strings."
                    ),
                ),
                FieldMetadata(keyword="CENTER_NAME"),
            ]

            ref_frame: Annotated[
                RefFrame | str,
                Field(
                    description=(
                        "Reference frame in which the ephemeris data are given. "
                        "Values outside the standard set should be documented in an ICD. "
                        "Parametric SANA B4 frames (e.g. ITRF2014, ICRF3) are supported via "
                        "RefFrame.parametric()."
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
                        "intrinsic to the frame definition. CCSDS date/time format (7.5.10)."
                    ),
                ),
                FieldMetadata(keyword="REF_FRAME_EPOCH"),
            ] = None

            time_system: Annotated[
                TimeSystem | str,
                Field(
                    description=(
                        "Time system used for ephemeris and covariance data. "
                        "Must remain fixed across all segments (5.2.4.5). "
                        "Values outside the standard set should be documented in an ICD. "
                        "If MET or MRT, the mission/event epoch should appear in a comment or ICD. "
                        "Timestamps should use three-digit day-of-duration format (7.5.10), "
                        "not calendar date format."
                    ),
                ),
                FieldMetadata(keyword="TIME_SYSTEM"),
            ]

            start_time: Annotated[
                CCSDSDate,
                Field(
                    description=(
                        "Start of TOTAL time span covered by ephemeris and covariance data "
                        "immediately following this metadata block. (7.5.10)."
                    ),
                ),
                FieldMetadata(keyword="START_TIME"),
            ]

            useable_start_time: Annotated[
                OptionalCCSDSDate,
                Field(
                    default=None,
                    description=(
                        "Start of USEABLE time span. Optional; allows fictitious leading "
                        "nodes for interpolation methods requiring more than two nodes. "
                        "Must be within [start_time, stop_time]. (7.5.10)."
                    ),
                ),
                FieldMetadata(keyword="USEABLE_START_TIME"),
            ] = None

            useable_stop_time: Annotated[
                OptionalCCSDSDate,
                Field(
                    default=None,
                    description=(
                        "Stop of USEABLE time span. Optional; allows fictitious trailing "
                        "nodes for interpolation methods requiring more than two nodes. "
                        "Must be within [start_time, stop_time]. Useable intervals across "
                        "consecutive segments must not overlap (except a shared endpoint). "
                        "(7.5.10)."
                    ),
                ),
                FieldMetadata(keyword="USEABLE_STOP_TIME"),
            ] = None

            stop_time: Annotated[
                CCSDSDate,
                Field(
                    description=(
                        "End of TOTAL time span covered by ephemeris and covariance data "
                        "immediately following this metadata block. (7.5.10)."
                    ),
                ),
                FieldMetadata(keyword="STOP_TIME"),
            ]

            interpolation: Annotated[
                Interpolation | str | None,
                Field(
                    default=None,
                    description=(
                        "Recommended interpolation method for ephemeris data. "
                        "Table 5-3 lists examples: HERMITE, LAGRANGE, LINEAR; "
                        "non-standard methods are accepted as plain strings. "
                        "interpolation_degree must be provided when set."
                    ),
                ),
                FieldMetadata(keyword="INTERPOLATION"),
            ] = None

            interpolation_degree: Annotated[
                int | None,
                Field(
                    default=None,
                    ge=1,
                    description=(
                        "Recommended interpolation degree. Integer greater than or equal to 1. "
                        "Mandatory when interpolation is set (5.2.3, table 5-3,). "
                        "The spec does not set an explicit minimum, but degree < 1 is "
                        "mathematically undefined for all supported interpolation methods."
                    ),
                ),
                FieldMetadata(keyword="INTERPOLATION_DEGREE"),
            ] = None

            @model_validator(mode="after")
            def validate_ref_frame_epoch_required(self) -> OEM.Segment.Metadata:
                _validate_ref_frame_epoch(self.ref_frame, self.ref_frame_epoch)
                return self

            @model_validator(mode="after")
            def validate_interpolation_degree_required(self) -> OEM.Segment.Metadata:
                if self.interpolation is not None and self.interpolation_degree is None:
                    raise ValueError(
                        "interpolation_degree is required when interpolation is set."
                    )
                return self

            @model_validator(mode="after")
            def validate_useable_times_within_total_span(self) -> OEM.Segment.Metadata:
                """
                Validate useable start/stop lie within [start_time, stop_time].

                (7.5.10) allows two epoch formats (calendar and DOY); _epoch_sort_key
                normalizes both to calendar format before comparison.
                """
                if self.useable_start_time is not None:
                    if _epoch_sort_key(self.useable_start_time) < _epoch_sort_key(self.start_time): # noqa: E501
                        raise ValueError(
                            "useable_start_time must not be earlier than start_time."
                        )
                    if _epoch_sort_key(self.useable_start_time) > _epoch_sort_key(self.stop_time): # noqa: E501
                        raise ValueError(
                            "useable_start_time must not be later than stop_time."
                        )
                if self.useable_stop_time is not None:
                    if _epoch_sort_key(self.useable_stop_time) > _epoch_sort_key(self.stop_time): # noqa: E501
                        raise ValueError(
                            "useable_stop_time must not be later than stop_time."
                        )
                    if _epoch_sort_key(self.useable_stop_time) < _epoch_sort_key(self.start_time): # noqa: E501
                        raise ValueError(
                            "useable_stop_time must not be earlier than start_time."
                        )
                if (
                    self.useable_start_time is not None
                    and self.useable_stop_time is not None
                    and _epoch_sort_key(self.useable_start_time)
                    > _epoch_sort_key(self.useable_stop_time)
                ):
                    raise ValueError(
                        "useable_start_time must not be later than useable_stop_time."
                    )
                return self

            @model_validator(mode="after")
            def validate_start_before_stop(self) -> OEM.Segment.Metadata:
                if _epoch_sort_key(self.start_time) >= _epoch_sort_key(self.stop_time):
                    raise ValueError("start_time must be earlier than stop_time.")
                return self

        class EphemerisData(BaseModel):
            """
            The list of ephemeris data lines for one segment.

            ``comment`` is allowed only at the beginning of the ephemeris data section
            (7.8.9); it must not appear between data lines.
            ``ephemeris_data_lines`` must be non-empty and ordered by increasing epoch.
            """

            model_config = CCSDS_MODEL_CONFIG

            # In string format, each set of ephemeris data, including the time tag,
            # must be provided on a single line. The order in which data items are given
            # shall be fixed: Epoch, X, Y, Z, X_DOT, Y_DOT, Z_DOT, X_DDOT, Y_DDOT, Z_DDOT.
            # At least one space character must be used to separate the items in each
            # ephemeris data line.
            class EphemerisDataLine(BaseModel):
                """
                One ephemeris data line: epoch + position + velocity + optional acceleration.

                Acceleration is all-or-nothing: if any component is provided, all three
                must be provided.

                Units: position [km], velocity [km/s], acceleration [km/s**2]. Units are not
                displayed in parsed OEM data lines.
                """

                model_config = CCSDS_MODEL_CONFIG

                _xml_tag: ClassVar[str] = "stateVector"

                epoch: Annotated[
                    CCSDSDate,
                    Field(description="Epoch of this state vector."),
                    FieldMetadata(keyword="EPOCH"),
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

                @model_validator(mode="after")
                def validate_acceleration_all_or_nothing(self) -> OEM.Segment.EphemerisData.EphemerisDataLine: # noqa: E501
                    components: tuple[float | None, float | None, float | None] = (
                        self.x_ddot,
                        self.y_ddot,
                        self.z_ddot,
                    )
                    present_components: list[float] = [c for c in components if c is not None]
                    if present_components and len(present_components) != 3:
                        raise ValueError(
                            "Acceleration components are all-or-nothing: provide all three "
                            "(x_ddot, y_ddot, z_ddot) or none."
                        )
                    return self

            comment: Comment = None

            ephemeris_data_lines: Annotated[
                list[OEM.Segment.EphemerisData.EphemerisDataLine],
                Field(
                    min_length=1,
                    description=(
                        "Ordered list of ephemeris data lines (increasing epoch). "
                        "At least one record is required."
                    ),
                ),
            ]

            @model_validator(mode="after")
            def validate_epochs_ordered(self) -> OEM.Segment.EphemerisData:
                epochs: list[str] = [state_vector.epoch for state_vector in self.ephemeris_data_lines]
                for i, (prev_epoch, current_epoch) in enumerate(
                    itertools.pairwise(epochs), start=1
                ):
                    if _epoch_sort_key(current_epoch) <= _epoch_sort_key(prev_epoch):
                        raise ValueError(
                            f"Ephemeris data line epochs must be strictly increasing. "
                            f"Found epoch[{i}]='{current_epoch}' <= epoch[{i - 1}]='{prev_epoch}'."
                        )
                return self

        class CovarianceMatrix(BaseModel):
            """
            The optional covariance matrix block that follows an ephemeris data block.

            Delimited by COVARIANCE_START / COVARIANCE_STOP in KVN. Contains one or
            more ``CovarianceMatrixLines`` entries ordered by increasing epoch.
            ``comment`` is allowed only at the beginning in KVN.
            """

            model_config = CCSDS_MODEL_CONFIG

            class CovarianceMatrixLines(BaseModel):
                """
                A single covariance matrix entry within the covariance block.

                Each entry has its own EPOCH and optional COV_REF_FRAME, followed by
                the 21 lower-triangular elements (rows 1-6, left to right).
                Units: km**2, km**2/s, km**2/s**2 (not in data lines).
                """

                model_config = CCSDS_MODEL_CONFIG

                _xml_tag: ClassVar[str] = "covarianceMatrix"

                epoch: Annotated[
                    CCSDSDate,
                    Field(description="Epoch of this covariance matrix."),
                    FieldMetadata(
                        keyword="EPOCH",
                        block_start=True,
                    ),
                ]

                cov_ref_frame: Annotated[
                    RefFrame | ManCovRefFrame | None,
                    Field(
                        default=None,
                        description=(
                            "Reference frame for this covariance matrix. "
                            "May be omitted if identical to the segment REF_FRAME. "
                            "Accepts standard reference frames or orbit-relative RSW/RTN/TNW."
                        ),
                    ),
                    FieldMetadata(keyword="COV_REF_FRAME"),
                ] = None

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
                        keyword="CX_DOT_X", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cx_dot_y: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [4,2]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_Y", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cx_dot_z: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [4,3]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_Z", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cx_dot_x_dot: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [4,4]. [km**2/s**2]",
                    ),
                    FieldMetadata(
                        keyword="CX_DOT_X_DOT", units="km**2/s**2", format_spec=" .15e"
                    ),
                ]

                # Row 5
                cy_dot_x: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [5,1]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_X", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cy_dot_y: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [5,2]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_Y", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cy_dot_z: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [5,3]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_Z", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cy_dot_x_dot: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [5,4]. [km**2/s**2]",
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_X_DOT", units="km**2/s**2", format_spec=" .15e"
                    ),
                ]

                cy_dot_y_dot: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [5,5]. [km**2/s**2]",
                    ),
                    FieldMetadata(
                        keyword="CY_DOT_Y_DOT", units="km**2/s**2", format_spec=" .15e"
                    ),
                ]

                # Row 6
                cz_dot_x: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [6,1]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_X", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cz_dot_y: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [6,2]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Y", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cz_dot_z: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [6,3]. [km**2/s]",
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Z", units="km**2/s", format_spec=" .15e"
                    ),
                ]

                cz_dot_x_dot: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [6,4]. [km**2/s**2]",
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_X_DOT", units="km**2/s**2", format_spec=" .15e"
                    ),
                ]

                cz_dot_y_dot: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [6,5]. [km**2/s**2]",
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Y_DOT", units="km**2/s**2", format_spec=" .15e"
                    ),
                ]

                cz_dot_z_dot: Annotated[
                    float,
                    Field(
                        description="Covariance matrix [6,6]. [km**2/s**2]",
                    ),
                    FieldMetadata(
                        keyword="CZ_DOT_Z_DOT", units="km**2/s**2", format_spec=" .15e"
                    ),
                ]

            _delineation: ClassVar[Delineation] = Delineation(
                "COVARIANCE_START", "COVARIANCE_STOP"
            )

            comment: Comment = None

            covariance_matrix_lines: Annotated[
                list[OEM.Segment.CovarianceMatrix.CovarianceMatrixLines],
                Field(
                    min_length=1,
                    description=(
                        "Ordered list of covariance matrix lines (increasing epoch,). "
                        "One per navigation solution is recommended."
                    ),
                ),
            ]

            @model_validator(mode="after")
            def validate_epochs_ordered(self) -> OEM.Segment.CovarianceMatrix:
                epochs: list[str] = [matrix_line.epoch for matrix_line in self.covariance_matrix_lines]
                for i, (prev_epoch, current_epoch) in enumerate(
                    itertools.pairwise(epochs), start=1
                ):
                    if _epoch_sort_key(current_epoch) <= _epoch_sort_key(prev_epoch):
                        raise ValueError(
                            f"Covariance matrix epochs must be strictly increasing. "
                            f"Found epoch[{i}]='{current_epoch}' <= "
                            f"epoch[{i - 1}]='{prev_epoch}'."
                        )
                return self

        metadata: Metadata
        ephemeris_data: EphemerisData
        covariance_matrix: CovarianceMatrix | None = Field(
            default=None,
            description=(
                "Optional covariance matrix block following the ephemeris data. "
                "Delimited by COVARIANCE_START / COVARIANCE_STOP in KVN (5.2.5,)."
            ),
        )

        @model_validator(mode="after")
        def validate_ephemeris_within_time_span(self) -> OEM.Segment:
            """
            Validate all ephemeris epochs lie within [start_time, stop_time].

            Allows calendar and DOY formats; _epoch_sort_key normalizes both.
            """
            start: str = _epoch_sort_key(self.metadata.start_time)
            stop: str = _epoch_sort_key(self.metadata.stop_time)
            for i, state_vector in enumerate(self.ephemeris_data.ephemeris_data_lines):
                key: str = _epoch_sort_key(state_vector.epoch)
                if key < start or key > stop:
                    raise ValueError(
                        f"Ephemeris data line epoch[{i}]='{state_vector.epoch}' lies outside the "
                        f"declared span [{self.metadata.start_time}, {self.metadata.stop_time}]."
                    )
            return self

        @model_validator(mode="after")
        def validate_covariance_within_time_span(self) -> OEM.Segment:
            if self.covariance_matrix is None:
                return self
            start: str = _epoch_sort_key(self.metadata.start_time)
            stop: str = _epoch_sort_key(self.metadata.stop_time)
            for i, matrix_line in enumerate(self.covariance_matrix.covariance_matrix_lines):
                key: str = _epoch_sort_key(matrix_line.epoch)
                if key < start or key > stop:
                    raise ValueError(
                        f"Covariance matrix epoch[{i}]='{matrix_line.epoch}' lies outside the "
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
                "CovarianceMatrix) segments. At least one segment is required."
            ),
        ),
    ]

    @classmethod
    def builder(cls) -> OEMBuilder:
        """
        Return a fluent builder for constructing this message type.

        Use ``model_copy(update={...})`` to create modified copies of a frozen instance.
        """
        return OEMBuilder()

    @model_validator(mode="after")
    def validate_time_system_fixed(self) -> OEM:
        systems: list[TimeSystem] = [seg.metadata.time_system for seg in self.segments]
        if len(set(systems)) > 1:
            distinct: str = ", ".join(str(s) for s in dict.fromkeys(systems))
            raise ValueError(
                f"TIME_SYSTEM must remain fixed across all segments (5.2.4.5). "
                f"Found: {distinct}."
            )
        return self

    @model_validator(mode="after")
    def validate_useable_intervals_non_overlapping(self) -> OEM:
        """
        Validate useable intervals across consecutive segments do not overlap.

        A shared endpoint is permitted (5.2.4.4). Only checked when both
        consecutive segments define useable bounds.
        """
        for i, (prev_segment, curr_segment) in enumerate(
            zip(self.segments, self.segments[1:], strict=False), start=1
        ):
            prev: OEM.Segment.Metadata = prev_segment.metadata
            curr: OEM.Segment.Metadata = curr_segment.metadata
            if (
                prev.useable_stop_time is not None
                and curr.useable_start_time is not None
                and _epoch_sort_key(curr.useable_start_time)
                < _epoch_sort_key(prev.useable_stop_time)
            ):
                raise ValueError(
                    f"Useable intervals of consecutive segments must not overlap. "
                    f"Segment {i - 1} useable stop='{prev.useable_stop_time}' > "
                    f"segment {i} useable start='{curr.useable_start_time}'."
                )
        return self


class OEMBuilder:
    """
    Call ``header`` once, then ``add_segment`` one or more times,
    then ``build`` to validate and return a frozen ``OEM`` instance.
    """

    def __init__(self) -> None:
        self._header_kwargs: dict[str, Any] = {}
        self._segments: list[OEM.Segment] = []

    def header(
        self,
        *,
        originator: str,
        creation_date: str | None = None,
        message_id: str | None = None,
        comment: list[str] | None = None,
    ) -> OEMBuilder:
        """
        Set header fields.

        Args:
            originator (str): Originator of the message.
            creation_date (str | None): CCSDS creation date string; defaults to the current UTC time.
            message_id (str | None): Optional message identifier.
            comment (list[str] | None): Optional list of comment strings.

        Returns:
            OEMBuilder
        """
        self._header_kwargs = {
            "ccsds_oem_vers": "3.0",
            "originator": originator,
            **({"creation_date": creation_date} if creation_date is not None else {}),
        }
        if message_id is not None:
            self._header_kwargs["message_id"] = message_id
        if comment is not None:
            self._header_kwargs["comment"] = comment
        return self

    def add_segment(
        self,
        metadata_kwargs: dict[str, Any],
        ephemeris_data_lines: list[dict[str, Any]],
        covariance_matrix_lines: list[dict[str, Any]] | None = None,
    ) -> OEMBuilder:
        """
        Append one segment to the message.

        Args:
            metadata_kwargs (dict[str, Any]): Keyword arguments for ``OEM.Segment.Metadata``.
                Required keys include `object_name`, `object_id`, `center_name`,
                `ref_frame`, `time_system`, `start_time`, and `stop_time`.
            ephemeris_data_lines (list[dict[str, Any]]): Non-empty list of dicts, each passed as keyword
                arguments to ``OEM.Segment.EphemerisData.EphemerisDataLine``.
                Required keys per line: `epoch`, `x`, `y`, `z`,
                `x_dot`, `y_dot`, `z_dot`.
            covariance_matrix_lines (list[dict[str, Any]] | None): Optional list of dicts, each passed as keyword
                arguments to ``OEM.Segment.CovarianceMatrix.CovarianceMatrixLines``.
                When provided, must be non-empty.

        Returns:
            OEMBuilder
        """
        segment_metadata: OEM.Segment.Metadata = OEM.Segment.Metadata(**metadata_kwargs)
        ephemeris_lines: list[OEM.Segment.EphemerisData.EphemerisDataLine] = [
            OEM.Segment.EphemerisData.EphemerisDataLine(**line)
            for line in ephemeris_data_lines
        ]
        ephemeris_data: OEM.Segment.EphemerisData = OEM.Segment.EphemerisData(
            ephemeris_data_lines=ephemeris_lines
        )

        covariance_matrix: OEM.Segment.CovarianceMatrix | None = None
        if covariance_matrix_lines is not None:
            covariance_lines: list[OEM.Segment.CovarianceMatrix.CovarianceMatrixLines] = [
                OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(**line)
                for line in covariance_matrix_lines
            ]
            covariance_matrix = OEM.Segment.CovarianceMatrix(
                covariance_matrix_lines=covariance_lines
            )

        self._segments.append(
            OEM.Segment(
                metadata=segment_metadata,
                ephemeris_data=ephemeris_data,
                covariance_matrix=covariance_matrix,
            )
        )
        return self

    def build(self) -> OEM:
        """
        Validate and return a frozen ``OEM`` instance.

        Returns:
            OEM

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        header_kw: dict[str, Any] = dict(self._header_kwargs)
        if "creation_date" not in header_kw:
            header_kw["creation_date"] = (
                datetime.now(UTC).strftime("%Y-%jT%H:%M:%S.%f")[:-3] + "Z"
            )
        return OEM(header=OEM.Header(**header_kw), segments=self._segments)
