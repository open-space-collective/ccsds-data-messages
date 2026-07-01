"""
Shared test infrastructure: factory helpers, assertion utilities, and common fixtures.

All per-message-type test files import from this module. Keep this file free of
domain-specific logic - just factories, assertion helpers, and constants.
"""

from __future__ import annotations

import difflib
import pprint
import re
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path
from typing import Any

import pytest

from ccsds_data_messages import OCM, OEM, OMM, OPM
from ccsds_data_messages.io.options import WriterOptions
from ccsds_data_messages.models.values import (
    CenterName,
    MeanElementTheory,
    RefFrame,
    TimeSystem,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXTURES: Path = Path(__file__).parent / "fixtures"
EPOCH: str = "2020-001T00:00:00"
CREATION_DATE: str = "2020-001T12:00:00"
_REL_TOLERANCE: float = 1e-9

# Per-fixture writer options - some spec fixtures use more decimal places than
# the model's default format_spec. These overrides ensure lossless round-trips.
_LOSSLESS_SV = WriterOptions(
    float_formats={
        "X": ".15g",
        "Y": ".15g",
        "Z": ".15g",
        "X_DOT": ".15g",
        "Y_DOT": ".15g",
        "Z_DOT": ".15g",
    }
)
FIXTURE_WRITE_OPTIONS: dict[str, WriterOptions] = {
    "opm_g2_maneuvers.kvn": _LOSSLESS_SV,
    "opm_g4_keplerian_covariance.kvn": _LOSSLESS_SV,
}


# ---------------------------------------------------------------------------
# Minimal-valid model factories
# ---------------------------------------------------------------------------


def make_opm(**overrides: Any) -> OPM:
    """Minimal valid OPM. Pass field overrides to header/metadata/state_vector."""
    header_kw = {
        "ccsds_opm_vers": "3.0",
        "creation_date": CREATION_DATE,
        "originator": "JAXA",
    }
    meta_kw = {
        "object_name": "TESTSAT",
        "object_id": "2020-001A",
        "center_name": CenterName.EARTH,
        "ref_frame": RefFrame.GCRF,
        "time_system": TimeSystem.UTC,
    }
    sv_kw = {
        "epoch": EPOCH,
        "x": 7000.0,
        "y": 100.0,
        "z": 200.0,
        "x_dot": 0.5,
        "y_dot": 7.5,
        "z_dot": 0.1,
    }
    header_kw.update(overrides.get("header", {}))
    meta_kw.update(overrides.get("metadata", {}))
    sv_kw.update(overrides.get("state_vector", {}))
    return OPM(
        header=OPM.Header(**header_kw),
        metadata=OPM.Metadata(**meta_kw),
        data=OPM.Data(state_vector=OPM.Data.StateVector(**sv_kw)),
    )


def make_omm(**overrides: Any) -> OMM:
    """Minimal valid OMM (DSST mean element theory)."""
    header_kw = {
        "ccsds_omm_vers": "3.0",
        "creation_date": CREATION_DATE,
        "originator": "JAXA",
    }
    meta_kw = {
        "object_name": "TESTSAT",
        "object_id": "2020-001A",
        "center_name": CenterName.EARTH,
        "ref_frame": RefFrame.GCRF,
        "time_system": TimeSystem.UTC,
        "mean_element_theory": MeanElementTheory.DSST,
    }
    mke_kw = {
        "epoch": EPOCH,
        "semi_major_axis": 7000.0,
        "eccentricity": 0.001,
        "inclination": 51.6,
        "ra_of_asc_node": 120.0,
        "arg_of_pericenter": 30.0,
        "mean_anomaly": 45.0,
    }
    header_kw.update(overrides.get("header", {}))
    meta_kw.update(overrides.get("metadata", {}))
    mke_kw.update(overrides.get("mean_keplerian_elements", {}))
    return OMM(
        header=OMM.Header(**header_kw),
        metadata=OMM.Metadata(**meta_kw),
        data=OMM.Data(mean_keplerian_elements=OMM.Data.MeanKeplerianElements(**mke_kw)),
    )


def make_oem(n_lines: int = 3, **overrides: Any) -> OEM:
    """Minimal valid OEM with one segment and n_lines ephemeris lines."""
    header_kw = {
        "ccsds_oem_vers": "3.0",
        "creation_date": CREATION_DATE,
        "originator": "JAXA",
    }
    epochs = [f"2020-001T00:{i * 10:02d}:00" for i in range(n_lines)]
    meta_kw = {
        "object_name": "TESTSAT",
        "object_id": "2020-001A",
        "center_name": CenterName.EARTH,
        "ref_frame": RefFrame.GCRF,
        "time_system": TimeSystem.UTC,
        "start_time": epochs[0],
        "stop_time": epochs[-1],
    }
    header_kw.update(overrides.get("header", {}))
    meta_kw.update(overrides.get("metadata", {}))
    lines = [
        OEM.Segment.EphemerisData.EphemerisDataLine(
            epoch=epochs[i],
            x=7000.0 - i * 50,
            y=i * 200.0,
            z=0.0,
            x_dot=-0.2 * i,
            y_dot=7.5,
            z_dot=0.0,
        )
        for i in range(n_lines)
    ]
    return OEM(
        header=OEM.Header(**header_kw),
        segments=[
            OEM.Segment(
                metadata=OEM.Segment.Metadata(**meta_kw),
                ephemeris_data=OEM.Segment.EphemerisData(ephemeris_data_lines=lines),
            )
        ],
    )


def make_ocm(**overrides: Any) -> OCM:
    """Minimal valid OCM (header + metadata only; no trajectory blocks)."""
    header_kw = {
        "ccsds_ocm_vers": "3.0",
        "creation_date": CREATION_DATE,
        "originator": "JAXA",
    }
    meta_kw = {
        "time_system": TimeSystem.UTC,
        "epoch_tzero": EPOCH,
    }
    header_kw.update(overrides.get("header", {}))
    meta_kw.update(overrides.get("metadata", {}))
    return OCM(
        header=OCM.Header(**header_kw),
        metadata=OCM.Metadata(**meta_kw),
    )


# ---------------------------------------------------------------------------
# Field-equality helpers
# ---------------------------------------------------------------------------


def assert_opm_equal(a: OPM, b: OPM) -> None:
    assert a.header.ccsds_opm_vers == b.header.ccsds_opm_vers
    assert a.header.originator == b.header.originator
    assert a.header.creation_date == b.header.creation_date
    assert a.metadata.object_name == b.metadata.object_name
    assert a.metadata.ref_frame == b.metadata.ref_frame
    assert a.metadata.time_system == b.metadata.time_system
    sv_a, sv_b = a.data.state_vector, b.data.state_vector
    assert sv_a.epoch == sv_b.epoch
    assert sv_a.x == pytest.approx(sv_b.x, rel=_REL_TOLERANCE)
    assert sv_a.y == pytest.approx(sv_b.y, rel=_REL_TOLERANCE)
    assert sv_a.z == pytest.approx(sv_b.z, rel=_REL_TOLERANCE)
    assert sv_a.x_dot == pytest.approx(sv_b.x_dot, rel=_REL_TOLERANCE)
    assert sv_a.y_dot == pytest.approx(sv_b.y_dot, rel=_REL_TOLERANCE)
    assert sv_a.z_dot == pytest.approx(sv_b.z_dot, rel=_REL_TOLERANCE)


def assert_omm_equal(a: OMM, b: OMM) -> None:
    assert a.header.originator == b.header.originator
    assert a.metadata.object_name == b.metadata.object_name
    assert a.metadata.mean_element_theory == b.metadata.mean_element_theory
    mke_a, mke_b = a.data.mean_keplerian_elements, b.data.mean_keplerian_elements
    assert mke_a.epoch == mke_b.epoch
    assert mke_a.eccentricity == pytest.approx(mke_b.eccentricity, rel=_REL_TOLERANCE)
    assert mke_a.inclination == pytest.approx(mke_b.inclination, rel=_REL_TOLERANCE)


def assert_oem_equal(a: OEM, b: OEM) -> None:
    assert a.header.originator == b.header.originator
    assert len(a.segments) == len(b.segments)
    for seg_a, seg_b in zip(a.segments, b.segments, strict=False):
        assert seg_a.metadata.object_name == seg_b.metadata.object_name
        assert seg_a.metadata.start_time == seg_b.metadata.start_time
        lines_a = seg_a.ephemeris_data.ephemeris_data_lines
        lines_b = seg_b.ephemeris_data.ephemeris_data_lines
        assert len(lines_a) == len(lines_b)
        for la, lb in zip(lines_a, lines_b, strict=False):
            assert la.epoch == lb.epoch
            assert la.x == pytest.approx(lb.x, rel=_REL_TOLERANCE)
            assert la.y == pytest.approx(lb.y, rel=_REL_TOLERANCE)
            assert la.z == pytest.approx(lb.z, rel=_REL_TOLERANCE)


# ---------------------------------------------------------------------------
# Semantic diff helpers (ported from test_spec_fixtures.py)
# ---------------------------------------------------------------------------

_FLOAT_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([Ee][+-]?\d+)?$")


def _norm_float(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s*\[.*?\]\s*$", "", value)
    if _FLOAT_RE.match(value):
        return str(float(value))
    return value


def _norm_data_line(line: str) -> str:
    parts = line.strip().split()
    if not parts:
        return ""
    if "T" in parts[0] and re.match(r"^\d{4}-", parts[0]):
        result = [parts[0]]
        result.extend(_norm_float(part) for part in parts[1:])
    else:
        result = [_norm_float(part) for part in parts]
    return " ".join(result)


def normalize_kvn(path: Path) -> list[str]:
    result: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("COMMENT"):
            _, _, text = stripped.partition("COMMENT")
            result.append(f"COMMENT {text.strip()}")
        elif "=" in stripped and not re.match(
            r"^(META|COVARIANCE|DATA|TRAJ|PHYS|COV|MAN|OD|USER)_(START|STOP)", stripped
        ):
            kw, _, val = stripped.partition("=")
            result.append(f"{kw.strip()} = {_norm_float(val)}")
        elif re.match(r"^[A-Z_]+(START|STOP)$", stripped):
            result.append(stripped)
        elif re.match(r"^\d{4}-", stripped) or re.match(r"^[+-]?\d", stripped):
            result.append(_norm_data_line(stripped))
        else:
            result.append(stripped)
    return result


def normalize_xml(path: Path) -> list[str]:
    result: list[str] = []
    tree = ET.parse(path)  # noqa: S314
    root = tree.getroot()

    def _visit(elem: ET.Element) -> None:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        for attr_name, attr_val in elem.attrib.items():
            if attr_name.startswith("{"):
                continue
            if attr_name == "units":
                continue
            result.append(f"{tag}@{attr_name} = {_norm_float(attr_val)}")
        text = (elem.text or "").strip()
        if text:
            result.append(f"{tag} = {_norm_float(text)}")
        for child in elem:
            _visit(child)

    _visit(root)
    return result


def assert_semantic_equal(expected: Path, actual: Path, fmt: str) -> None:
    """Fail with a unified diff if the two files differ semantically."""
    normalize = normalize_kvn if fmt == "kvn" else normalize_xml
    exp_lines = normalize(expected)
    act_lines = normalize(actual)
    diff = list(
        difflib.unified_diff(
            exp_lines,
            act_lines,
            fromfile=f"spec/{expected.name}",
            tofile=f"written/{actual.name}",
            lineterm="",
        )
    )
    if diff:
        pytest.fail("Semantic diff:\n" + "\n".join(diff))


def _approx_equal(left: Any, right: Any, rel: float = 1e-9) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        if left == right:
            return True
        denom = max(abs(left), abs(right), 1e-300)
        return abs(left - right) / denom <= rel
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_approx_equal(left[key], right[key], rel) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(
            _approx_equal(li, ri, rel) for li, ri in zip(left, right, strict=False)
        )
    return left == right


def assert_models_equal(left: Any, right: Any) -> None:
    """Assert two domain model instances are semantically equal (floats ≈ 1e-9)."""
    left_dump = left.model_dump()
    right_dump = right.model_dump()
    if not _approx_equal(left_dump, right_dump):
        diff = list(
            difflib.unified_diff(
                pprint.pformat(left_dump).splitlines(),
                pprint.pformat(right_dump).splitlines(),
                fromfile="model_a",
                tofile="model_b",
                lineterm="",
            )
        )
        pytest.fail("Model mismatch:\n" + "\n".join(diff))
