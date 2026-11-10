# SPDX-License-Identifier: Apache-2.0

"""
Type-to-type conversions between CCSDS data message models.

These functions are pure domain transformations: they accept a validated message
instance of one type and return a validated instance of another type. No IO is
involved; all fields are mapped according to the CCSDS 502.0-B-3 specification.
"""

from __future__ import annotations

from typing import Any

from ._epoch import _normalize_epoch
from ._fields import FieldMetadata
from ._tle_codec import _encode_lines
from ._tle_codec import _TleFields
from .ocm import OCM
from .oem import OEM
from .omm import OMM
from .tle import TLE
from .values import CenterName
from .values import CovarianceOrdering
from .values import ExtendedManCovRefFrame
from .values import ManCovRefFrame
from .values import MeanElementTheory
from .values import OrbitalElements
from .values import RefFrame

_VALID_TRAJ_BASIS = frozenset({"OPERATIONAL", "CANDIDATE"})

# OEM COV_REF_FRAME -> OCM COV_REF_FRAME. TraCSS-Spec-002 table 6 only accepts the
# inertial orbit-relative frames TNW_INERTIAL and RSW_INERTIAL; RSW and RTN are two
# names for the same radial/transverse/normal frame, so both map to RSW_INERTIAL.
# The two TraCSS frames map to themselves. Any other OEM covariance frame (including
# the segment REF_FRAME, e.g. EME2000, used when a line has no COV_REF_FRAME) is
# rejected by oem_to_tracss_ocm.
COV_REF_FRAME_MAPPING: dict[str, ExtendedManCovRefFrame] = {
    ManCovRefFrame.RSW: ExtendedManCovRefFrame.RSW_INERTIAL,
    ManCovRefFrame.RTN: ExtendedManCovRefFrame.RSW_INERTIAL,
    ManCovRefFrame.TNW: ExtendedManCovRefFrame.TNW_INERTIAL,
    ExtendedManCovRefFrame.RSW_INERTIAL: ExtendedManCovRefFrame.RSW_INERTIAL,
    ExtendedManCovRefFrame.TNW_INERTIAL: ExtendedManCovRefFrame.TNW_INERTIAL,
}

# Format specs are read from the same FieldMetadata annotations that
# io/kvn/oem_writer.py uses, so this stays in sync with the canonical OEM writer
# instead of re-deriving its own copy of the format strings.
_EPHEMERIS_DATA_LINE = OEM.Segment.EphemerisData.EphemerisDataLine
_EPHEMERIS_FORMAT_SPECS: dict[str, str | None] = {
    fn: next((m.format_spec for m in fi.metadata if isinstance(m, FieldMetadata)), None)
    for fn, fi in _EPHEMERIS_DATA_LINE.model_fields.items()
}

_COVARIANCE_MATRIX_LINES = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines
_COV_FIELD_ORDER: list[str] = [
    fn
    for fn in _COVARIANCE_MATRIX_LINES.model_fields
    if fn not in ("epoch", "cov_ref_frame")
]
_COVARIANCE_FORMAT_SPEC: str | None = next(
    (
        m.format_spec
        for m in _COVARIANCE_MATRIX_LINES.model_fields[_COV_FIELD_ORDER[0]].metadata
        if isinstance(m, FieldMetadata)
    ),
    None,
)


def _fmt(value: float, spec: str | None) -> str:
    # Mirrors io/_utils.py:format_value's fallback: fields with no explicit
    # format_spec (e.g. EphemerisDataLine.x_ddot/y_ddot/z_ddot) use ".15g"
    # (section 7.5.6-7.5.7: max 16 significant digits).
    return format(value, spec) if spec is not None else format(value, ".15g")


def oem_to_tracss_ocm(
    oem: OEM,
    *,
    traj_basis: str,
    object_designator: str,
    operator: str,
    owner: str,
    country: str,
    originator_address: str,
    originator_email: str,
    originator_phone: str,
    message_id: str | None = None,
    useable_record_padding: int = 5,
) -> OCM:
    """
    Convert an OEM to a TraCSS-compliant OCM (TraCSS-Spec-002 v2.1).

    Each OEM segment becomes one ``OCM.TrajectoryStateTimeHistory`` block with
    ``TRAJ_TYPE = CARTPV`` (or ``CARTPVA`` when acceleration components are
    present). When the OEM carries covariance, each segment produces exactly one
    ``OCM.CovarianceTimeHistory`` block with ``COV_TYPE = CARTPV`` and
    ``COV_ORDERING = LTM``, its ``COV_REF_FRAME`` translated through
    ``COV_REF_FRAME_MAPPING``.

    The OCM ``EPOCH_TZERO`` is set to the epoch of the first ephemeris data line.
    Header fields are taken from the OEM; ``OEM.validate_single_object`` (section 5.1.3)
    already guarantees every segment agrees on ``object_name`` and ``object_id``.

    Covariance note: TraCSS-Spec-002 (table 1 and section 7) pairs every orbit data
    section with one covariance data section, line for line with identical epochs. OEM
    covariance that cannot be expressed that way (missing in some segments, at epochs
    other than the ephemeris epochs, or in several frames) is rejected rather than
    split into extra blocks.

    All parameters marked (M) are mandatory per the TraCSS OCM spec.

    Args:
        oem: A validated :class:`OEM` instance. All segments must use
            ``CENTER_NAME = EARTH`` and ``REF_FRAME = EME2000``.
        traj_basis (M): ``"OPERATIONAL"`` or ``"CANDIDATE"``.
        object_designator (M): DoD Satellite Catalog Number (or ``"UNKNOWN"``).
        operator (M): Operating organization registered with TraCSS.
        owner (M): Owning organization registered with TraCSS.
        country (M): ISO 3166 country code or name (or ``"UNKNOWN"``).
        originator_address (M): Originator mailing address.
        originator_email (M): Originator e-mail address.
        originator_phone (M): Originator phone number.
        message_id: Unique message identifier. Falls back to the OEM header's
            ``message_id`` when not supplied. One of the two must be present;
            TraCSS recommends ``OBJECT_DESIGNATOR + "_" + CREATION_DATE``.
        useable_record_padding: Number of data lines at each edge to treat as
            non-useable. ``USEABLE_START_TIME`` is set to
            ``lines[padding].epoch`` and ``USEABLE_STOP_TIME`` to
            ``lines[-(padding+1)].epoch``. TraCSS requires >=5 lines on each
            side, so each segment must have at least
            ``2 * useable_record_padding + 1`` data lines. Default ``5``.

    Returns:
        A validated :class:`OCM` instance compliant with TraCSS-Spec-002.

    Raises:
        ValueError: If ``traj_basis`` is not ``"OPERATIONAL"`` or ``"CANDIDATE"``.
        ValueError: If no ``message_id`` is available from param or OEM header.
        ValueError: If any segment uses ``CENTER_NAME != EARTH``.
        ValueError: If any segment uses ``REF_FRAME != EME2000``.
        ValueError: If any segment has too few data lines to compute useable times.
        ValueError: If only some segments carry covariance.
        ValueError: If a segment's covariance epochs do not match its ephemeris epochs
            one-to-one.
        ValueError: If a covariance frame is not in ``COV_REF_FRAME_MAPPING`` (e.g. the
            segment REF_FRAME ``EME2000`` when a line has no ``COV_REF_FRAME``).
        ValueError: If a segment's covariance uses more than one frame, or segments use
            different covariance frames (after ``COV_REF_FRAME_MAPPING``).
    """
    if traj_basis not in _VALID_TRAJ_BASIS:
        raise ValueError(
            f"traj_basis must be one of {sorted(_VALID_TRAJ_BASIS)!r}, got {traj_basis!r}."
        )

    if (effective_message_id := message_id or oem.header.message_id) is None:
        raise ValueError(
            "TraCSS requires MESSAGE_ID. Supply message_id= or ensure the OEM header has one."
        )

    # OEM.validate_single_object (section 5.1.3) already guarantees every segment agrees
    # on object_name and object_id at construction time - unreachable here.
    first_seg = oem.segments[0]

    for i, seg in enumerate(oem.segments):
        if seg.metadata.center_name != CenterName.EARTH:
            raise ValueError(
                f"TraCSS requires CENTER_NAME = EARTH; segment {i} has {seg.metadata.center_name!r}."
            )
        if seg.metadata.ref_frame != RefFrame.EME2000:
            raise ValueError(
                f"TraCSS requires TRAJ_REF_FRAME = EME2000; segment {i} has {seg.metadata.ref_frame!r}."
            )

    cov_frames = _check_tracss_covariance_consistency(oem)

    header = OCM.Header(
        ccsds_ocm_vers="3.0",
        originator=oem.header.originator,
        creation_date=oem.header.creation_date,
        message_id=effective_message_id,
        **({"comment": oem.header.comment} if oem.header.comment is not None else {}),
    )

    trajectory_states = [
        _segment_to_traj(
            seg,
            traj_id=str(i + 1),
            traj_basis=traj_basis,
            useable_record_padding=useable_record_padding,
        )
        for i, seg in enumerate(oem.segments)
    ]

    useable_start_times: list[str] = []
    useable_stop_times: list[str] = []
    for i, traj in enumerate(trajectory_states):
        if traj.useable_start_time is None or traj.useable_stop_time is None:
            raise ValueError(
                f"TRAJ block {i + 1} has no USEABLE_START/STOP_TIME. "
                f"Each segment needs at least {2 * useable_record_padding + 1} data lines "
                f"(useable_record_padding={useable_record_padding})."
            )
        useable_start_times.append(traj.useable_start_time)
        useable_stop_times.append(traj.useable_stop_time)

    # One covariance block per segment (validated above), so COV_ID i pairs with TRAJ_ID i.
    raw_covariances = [
        _segment_to_cov_block(seg, cov_id=str(i + 1), cov_ref_frame=frame)
        for i, (seg, frame) in enumerate(zip(oem.segments, cov_frames, strict=True))
        if frame is not None
    ]

    elements = ["ORB"] * len(trajectory_states) + ["COV"] * len(raw_covariances)
    ocm_data_elements = ", ".join(elements) or None

    # useable_start_times/useable_stop_times are narrowed to str by the validation loop above.
    start_time = min(useable_start_times, key=_normalize_epoch)
    stop_time = max(useable_stop_times, key=_normalize_epoch)

    metadata = OCM.Metadata(
        object_name=first_seg.metadata.object_name,
        international_designator=first_seg.metadata.object_id,
        object_designator=object_designator,
        operator=operator,
        owner=owner,
        country=country,
        originator_address=originator_address,
        originator_email=originator_email,
        originator_phone=originator_phone,
        time_system=first_seg.metadata.time_system,
        epoch_tzero=first_seg.ephemeris_data.ephemeris_data_lines[0].epoch,
        start_time=start_time,
        stop_time=stop_time,
        ocm_data_elements=ocm_data_elements,
    )

    return OCM(
        header=header,
        metadata=metadata,
        trajectory_states=trajectory_states,
        covariances=raw_covariances or None,
    )


_TRAJ_UNITS = {
    OrbitalElements.CARTPV: "[km,km,km,km/s,km/s,km/s]",
    OrbitalElements.CARTPVA: "[km,km,km,km/s,km/s,km/s,km/s**2,km/s**2,km/s**2]",
}

_COV_UNITS = {
    OrbitalElements.CARTPV: "[km,km,km,km/s,km/s,km/s]",
}


def _segment_to_traj(
    seg: OEM.Segment,
    traj_id: str,
    traj_basis: str | None,
    useable_record_padding: int,
) -> OCM.TrajectoryStateTimeHistory:
    lines = seg.ephemeris_data.ephemeris_data_lines
    has_accel = any(line.x_ddot is not None for line in lines)
    traj_type = OrbitalElements.CARTPVA if has_accel else OrbitalElements.CARTPV

    kwargs: dict[str, Any] = {
        "traj_id": traj_id,
        "center_name": seg.metadata.center_name,
        "traj_ref_frame": seg.metadata.ref_frame,
        "traj_type": traj_type,
        "traj_units": _TRAJ_UNITS[traj_type],
        "data_lines": [_format_ephemeris_line(line) for line in lines],
    }
    if traj_basis is not None:
        kwargs["traj_basis"] = traj_basis
    if seg.metadata.ref_frame_epoch is not None:
        kwargs["traj_frame_epoch"] = seg.metadata.ref_frame_epoch
    if seg.metadata.interpolation is not None:
        kwargs["interpolation"] = seg.metadata.interpolation
    if seg.metadata.interpolation_degree is not None:
        kwargs["interpolation_degree"] = seg.metadata.interpolation_degree

    if useable_record_padding > 0:
        # Always recompute from data lines when padding is requested; the OEM's
        # own useable_start/stop may sit at the first/last record which violates
        # the requirement for >=padding preceding/following lines.
        if len(lines) > 2 * useable_record_padding:
            kwargs["useable_start_time"] = lines[useable_record_padding].epoch
            kwargs["useable_stop_time"] = lines[-(useable_record_padding + 1)].epoch
    else:
        if seg.metadata.useable_start_time is not None:
            kwargs["useable_start_time"] = seg.metadata.useable_start_time
        if seg.metadata.useable_stop_time is not None:
            kwargs["useable_stop_time"] = seg.metadata.useable_stop_time

    return OCM.TrajectoryStateTimeHistory(**kwargs)


_CovFrame = RefFrame | ManCovRefFrame | ExtendedManCovRefFrame | str


def _segment_cov_frames(seg_index: int, seg: OEM.Segment) -> list[ExtendedManCovRefFrame]:
    """
    Effective OCM COV_REF_FRAME of each covariance line in ``seg``, in line order.

    A line without its own COV_REF_FRAME uses the segment REF_FRAME; every frame is then
    translated through ``COV_REF_FRAME_MAPPING``.

    Raises:
        ValueError: If a line's frame is not a key of ``COV_REF_FRAME_MAPPING``.
    """
    assert seg.covariance_matrix is not None  # noqa: S101 (callers check this first)
    frames: list[ExtendedManCovRefFrame] = []
    for line_index, line in enumerate(seg.covariance_matrix.covariance_matrix_lines):
        if line.cov_ref_frame is not None:
            oem_frame, source = line.cov_ref_frame, "its COV_REF_FRAME"
        else:
            oem_frame, source = (
                seg.metadata.ref_frame,
                "the segment REF_FRAME (no COV_REF_FRAME)",
            )
        if (ocm_frame := COV_REF_FRAME_MAPPING.get(oem_frame)) is None:
            supported = ", ".join(
                f"{oem} -> {ocm}" for oem, ocm in COV_REF_FRAME_MAPPING.items()
            )
            raise ValueError(
                f"Segment {seg_index} covariance line {line_index} "
                f"(epoch {line.epoch}) uses frame {str(oem_frame)!r} from {source}, "
                "which cannot be mapped to a TraCSS covariance frame "
                "(TraCSS-Spec-002 table 6 accepts RSW_INERTIAL or TNW_INERTIAL). "
                f"Supported OEM covariance frames: {supported}."
            )
        frames.append(ocm_frame)
    return frames


def _check_tracss_covariance_consistency(oem: OEM) -> list[_CovFrame | None]:
    """
    Enforce the TraCSS-Spec-002 pairing rules between orbit and covariance data.

    - Table 1: if covariance is provided, there is one covariance section per orbit data
      section, covering the same time span - so either every segment has covariance or
      none does.
    - Section 7: one-to-one correspondence between orbit and covariance lines within each
      pair of sections, with identical epochs.
    - Table 6: one COV_REF_FRAME per covariance section, so each segment's covariance must
      resolve to a single frame (after ``COV_REF_FRAME_MAPPING``). All segments must also
      agree on that frame, so the message has one consistent covariance frame.

    Returns:
        The (mapped) covariance frame of each segment, or ``None`` per segment when the
        OEM carries no covariance at all.
    """
    with_cov = [
        i for i, seg in enumerate(oem.segments) if seg.covariance_matrix is not None
    ]
    if not with_cov:
        return [None] * len(oem.segments)
    if len(with_cov) != len(oem.segments):
        without_cov = sorted(set(range(len(oem.segments))) - set(with_cov))
        raise ValueError(
            "TraCSS requires one covariance section per orbit data section (table 1): "
            f"segments {with_cov} have covariance but segments {without_cov} do not."
        )

    seg_frames: list[_CovFrame | None] = []
    for i, seg in enumerate(oem.segments):
        assert seg.covariance_matrix is not None  # noqa: S101 (checked above)
        eph_epochs = [
            _normalize_epoch(line.epoch)
            for line in seg.ephemeris_data.ephemeris_data_lines
        ]
        cov_epochs = [
            _normalize_epoch(line.epoch)
            for line in seg.covariance_matrix.covariance_matrix_lines
        ]
        if len(cov_epochs) != len(eph_epochs):
            raise ValueError(
                "TraCSS requires one covariance line per orbit data line (section 7); "
                f"segment {i} has {len(cov_epochs)} covariance lines for "
                f"{len(eph_epochs)} ephemeris lines."
            )
        if cov_epochs != eph_epochs:
            mismatch = next(
                k
                for k, (c, e) in enumerate(zip(cov_epochs, eph_epochs, strict=True))
                if c != e
            )
            raise ValueError(
                "TraCSS requires covariance and orbit data lines to have identical epochs "
                f"(section 7); segment {i} line {mismatch} has covariance epoch "
                f"{seg.covariance_matrix.covariance_matrix_lines[mismatch].epoch!r} but "
                f"ephemeris epoch {seg.ephemeris_data.ephemeris_data_lines[mismatch].epoch!r}."
            )

        frames = set(_segment_cov_frames(i, seg))
        if len(frames) != 1:
            raise ValueError(
                "TraCSS allows one COV_REF_FRAME per covariance section (table 6); "
                f"segment {i} mixes covariance frames {sorted(map(str, frames))}."
            )
        seg_frames.append(frames.pop())

    if len(set(seg_frames)) != 1:
        raise ValueError(
            "All segments must use the same covariance frame; got "
            f"{[str(f) for f in seg_frames]} for segments 0..{len(seg_frames) - 1}."
        )
    return seg_frames


def _segment_to_cov_block(
    seg: OEM.Segment,
    cov_id: str,
    cov_ref_frame: _CovFrame,
) -> OCM.CovarianceTimeHistory:
    """
    Convert one OEM segment's covariance into a single OCM CovarianceTimeHistory block.

    The caller has already checked the segment against the TraCSS pairing rules
    (``_check_tracss_covariance_consistency``) and resolved its single, mapped frame.

    Note: the frame is only relabelled. Going from a rotating frame (RSW/RTN, TNW) to its
    inertial counterpart leaves the position terms unchanged but, strictly, changes the
    velocity terms by the omega x r contribution, which is not applied here.
    """
    assert seg.covariance_matrix is not None  # noqa: S101 (caller filters this; see call site)
    return OCM.CovarianceTimeHistory(
        cov_id=cov_id,
        cov_ref_frame=cov_ref_frame,
        cov_type=OrbitalElements.CARTPV,
        cov_ordering=CovarianceOrdering.LTM,
        cov_units=_COV_UNITS[OrbitalElements.CARTPV],
        data_lines=[
            _format_cov_line(line)
            for line in seg.covariance_matrix.covariance_matrix_lines
        ],
    )


def _format_ephemeris_line(line: OEM.Segment.EphemerisData.EphemerisDataLine) -> str:
    parts = [
        line.epoch,
        _fmt(line.x, _EPHEMERIS_FORMAT_SPECS["x"]),
        _fmt(line.y, _EPHEMERIS_FORMAT_SPECS["y"]),
        _fmt(line.z, _EPHEMERIS_FORMAT_SPECS["z"]),
        _fmt(line.x_dot, _EPHEMERIS_FORMAT_SPECS["x_dot"]),
        _fmt(line.y_dot, _EPHEMERIS_FORMAT_SPECS["y_dot"]),
        _fmt(line.z_dot, _EPHEMERIS_FORMAT_SPECS["z_dot"]),
    ]
    # validate_acceleration_all_or_nothing (models/oem.py) guarantees these three are
    # either all None or all non-None; checking all three (not just x_ddot) narrows
    # each individually instead of relying on that invariant implicitly.
    if line.x_ddot is not None and line.y_ddot is not None and line.z_ddot is not None:
        parts += [
            _fmt(line.x_ddot, _EPHEMERIS_FORMAT_SPECS["x_ddot"]),
            _fmt(line.y_ddot, _EPHEMERIS_FORMAT_SPECS["y_ddot"]),
            _fmt(line.z_ddot, _EPHEMERIS_FORMAT_SPECS["z_ddot"]),
        ]
    return " ".join(parts)


def _format_cov_line(line: OEM.Segment.CovarianceMatrix.CovarianceMatrixLines) -> str:
    elements = [
        line.cx_x,
        line.cy_x,
        line.cy_y,
        line.cz_x,
        line.cz_y,
        line.cz_z,
        line.cx_dot_x,
        line.cx_dot_y,
        line.cx_dot_z,
        line.cx_dot_x_dot,
        line.cy_dot_x,
        line.cy_dot_y,
        line.cy_dot_z,
        line.cy_dot_x_dot,
        line.cy_dot_y_dot,
        line.cz_dot_x,
        line.cz_dot_y,
        line.cz_dot_z,
        line.cz_dot_x_dot,
        line.cz_dot_y_dot,
        line.cz_dot_z_dot,
    ]
    return line.epoch + " " + " ".join(_fmt(e, _COVARIANCE_FORMAT_SPEC) for e in elements)


# Mean element theories that cannot round-trip to a classic NORAD TLE: DSST/USM do
# not populate the TLE fields, and SGP4-XP carries BTERM/AGOM drag and SRP terms that
# the standard two-line format has no columns for.
_TLE_INCOMPATIBLE_THEORIES = frozenset(
    {
        MeanElementTheory.SGP4_XP,
        MeanElementTheory.DSST,
        MeanElementTheory.USM,
    }
)


def omm_to_tle(omm: OMM) -> TLE:
    """
    Convert an OMM to a NORAD Two-Line Element set (TLE).

    Returns a :class:`~ccsds_data_messages.models.tle.TLE` value object with the
    Alpha-5 satellite-number encoding. ``str(tle)`` gives the two-line form and
    ``tle.three_line()`` prepends the space-track ``"0 NAME"`` title line. The
    fixed-column encoding is handled by ``models/_tle_codec.py``.

    ``MEAN_MOTION_DOT`` and ``MEAN_MOTION_DDOT`` are written to the TLE first/second
    derivative fields unchanged: they already hold the SGP Taylor-series terms
    (n-dot/2 and n-ddot/6). Missing optional fields default per de-facto TLE
    convention: ``CLASSIFICATION_TYPE`` to ``U``, ``EPHEMERIS_TYPE`` to ``0``, and
    absent BSTAR / derivative / element-set / revolution values to zero.

    Args:
        omm: A validated :class:`OMM`. Must provide ``MEAN_MOTION`` (not only
            ``SEMI_MAJOR_AXIS``) and a ``tle_related_parameters`` block with a
            ``NORAD_CAT_ID``.

    Returns:
        A :class:`TLE` value object.

    Raises:
        ValueError: If ``MEAN_ELEMENT_THEORY`` is DSST, USM, or SGP4-XP (or BTERM is
            present); if ``MEAN_MOTION`` is absent; if the TLE-related block or
            ``NORAD_CAT_ID`` is absent; or if ``NORAD_CAT_ID`` exceeds the Alpha-5
            maximum (339999).
    """
    line1, line2 = _encode_lines(_omm_to_tle_fields(omm))
    return TLE(name=omm.metadata.object_name, line1=line1, line2=line2)


def _omm_to_tle_fields(omm: OMM) -> _TleFields:
    """Map a convertible OMM onto ``_TleFields``, raising ``ValueError`` otherwise."""
    if omm.metadata.mean_element_theory in _TLE_INCOMPATIBLE_THEORIES:
        raise ValueError(
            f"MEAN_ELEMENT_THEORY={omm.metadata.mean_element_theory} cannot be "
            "represented as a classic NORAD TLE."
        )

    mke = omm.data.mean_keplerian_elements
    if (mean_motion := mke.mean_motion) is None:
        raise ValueError(
            "MEAN_MOTION is required to generate a TLE; this OMM provides only "
            "SEMI_MAJOR_AXIS."
        )

    tle = omm.data.tle_related_parameters
    if tle is None or tle.norad_cat_id is None:
        raise ValueError(
            "tle_related_parameters with NORAD_CAT_ID is required to generate a TLE."
        )
    if tle.bterm is not None:
        raise ValueError(
            "OMMs using the SGP4-XP ballistic coefficient (BTERM) cannot be "
            "represented as a classic NORAD TLE."
        )

    return _TleFields(
        norad_cat_id=tle.norad_cat_id,
        classification=(tle.classification_type or "U")[0],
        international_designator=omm.metadata.object_id,
        epoch=mke.epoch,
        time_system=omm.metadata.time_system,
        n_dot=tle.mean_motion_dot or 0.0,
        n_ddot=tle.mean_motion_ddot or 0.0,
        bstar=tle.bstar or 0.0,
        ephemeris_type=tle.ephemeris_type or 0,
        element_set_no=tle.element_set_no or 0,
        inclination=mke.inclination,
        ra_of_asc_node=mke.ra_of_asc_node,
        eccentricity=mke.eccentricity,
        arg_of_pericenter=mke.arg_of_pericenter,
        mean_anomaly=mke.mean_anomaly,
        mean_motion=mean_motion,
        rev_at_epoch=tle.rev_at_epoch or 0,
    )
