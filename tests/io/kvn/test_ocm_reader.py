"""
Unit tests for the KVN OCM reader adapter.

Instantiates ``KVNOCMReader`` directly (as opposed to the high-level
``read()`` dispatch tested in ``tests/io/test_reader.py``) and exercises
``read()`` / ``read_string()`` against the OCM KVN spec fixtures.

Module under test:
  src/ccsds_data_messages/io/kvn/ocm_reader.py
"""

from __future__ import annotations

import pytest
from conftest import FIXTURES

from ccsds_data_messages import OCM
from ccsds_data_messages import read_string
from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.exceptions import SpecViolationError
from ccsds_data_messages.io.kvn.ocm_reader import KVNOCMReader

_KVN_FIXTURES: list[str] = [
    "ocm_g15_minimal.kvn",
    "ocm_g16_characteristics.kvn",
    "ocm_g17_deployments.kvn",
    "ocm_g18_multi_traj.kvn",
    "ocm_g19_covariance_histories.kvn",
]


class TestKVNOCMReader:
    def test_read_returns_ocm_instance(self):
        reader = KVNOCMReader()
        msg = reader.read(FIXTURES / "ocm_g15_minimal.kvn")
        assert isinstance(msg, OCM)

    def test_read_populates_stable_fields(self):
        reader = KVNOCMReader()
        msg = reader.read(FIXTURES / "ocm_g15_minimal.kvn")
        assert msg.header.originator == "JAXA"
        assert str(msg.metadata.time_system) == "UTC"
        assert msg.metadata.epoch_tzero == "2022-12-18T14:28:15.1172"

    def test_read_parses_trajectory_state_history(self):
        """The minimal fixture carries a single CARTPV trajectory block."""
        reader = KVNOCMReader()
        msg = reader.read(FIXTURES / "ocm_g15_minimal.kvn")
        assert msg.trajectory_states is not None
        assert len(msg.trajectory_states) == 1
        traj = msg.trajectory_states[0]
        assert str(traj.center_name) == "EARTH"
        assert str(traj.traj_ref_frame) == "ITRF2000"
        assert str(traj.traj_type) == "CARTPV"
        assert len(traj.data_lines) == 4

    def test_read_richer_fixture_parses_multiple_trajectory_blocks(self):
        """The multi-trajectory fixture carries two TRAJ blocks."""
        reader = KVNOCMReader()
        msg = reader.read(FIXTURES / "ocm_g18_multi_traj.kvn")
        assert msg.metadata.object_name == "OSPREY 5"
        assert msg.trajectory_states is not None
        assert len(msg.trajectory_states) == 2

    @pytest.mark.parametrize("fixture", _KVN_FIXTURES)
    def test_read_all_fixtures_return_ocm(self, fixture: str):
        reader = KVNOCMReader()
        msg = reader.read(FIXTURES / fixture)
        assert isinstance(msg, OCM)

    @pytest.mark.parametrize("fixture", _KVN_FIXTURES)
    def test_read_string_matches_read(self, fixture: str):
        reader = KVNOCMReader()
        path = FIXTURES / fixture
        from_path = reader.read(path)
        from_string = reader.read_string(path.read_text(encoding="utf-8"))
        assert isinstance(from_string, OCM)
        assert from_string.header.originator == from_path.header.originator
        assert from_string.metadata.epoch_tzero == from_path.metadata.epoch_tzero
        assert from_string.model_dump() == from_path.model_dump()


class TestKVNOCMManeuverRows:
    """
    Maneuver data lines are parsed into typed rows keyed by MAN_COMPOSITION.

    The column arity check and per-element constraints (table 6-8/6-9) live on this
    parse path now that ``data_lines`` holds typed rows rather than raw strings.
    """

    def test_maneuver_lines_parsed_as_typed_deployment_rows(self):
        msg = KVNOCMReader().read(FIXTURES / "ocm_g17_deployments.kvn")
        assert msg.maneuvers is not None
        row = msg.maneuvers[0].data_lines[0]
        assert isinstance(row, OCM.ManeuverSpecification.DeploymentDataLine)
        assert row.deploy_id == "CUBESAT_10"
        assert row.deploy_mass == -1.0

    def test_wrong_column_count_raises_parse_error(self):
        text = (FIXTURES / "ocm_g17_deployments.kvn").read_text(encoding="utf-8")
        # Append an extra value to the propulsive maneuver line (9 columns -> 10).
        malformed = text.replace(
            "2022-12-18T14:36:35.1172 100.0 0.0 0.5 0.0 0.95 ON 300.0 5.0",
            "2022-12-18T14:36:35.1172 100.0 0.0 0.5 0.0 0.95 ON 300.0 5.0 9.9",
        )
        assert malformed != text
        with pytest.raises(ParseError):
            KVNOCMReader().read_string(malformed)

    def test_positive_deploy_mass_rejected_as_spec_violation(self):
        text = (FIXTURES / "ocm_g17_deployments.kvn").read_text(encoding="utf-8")
        # DEPLOY_MASS is a host-mass decrement (table 6-9: shall be <= 0.0); flip the
        # CUBESAT_10 row's -1.0 to +1.0. The high-level read_string surfaces the
        # per-element ValidationError as SpecViolationError.
        malformed = text.replace("-1.0 5.0 -0.005025", "1.0 5.0 -0.005025")
        assert malformed != text
        with pytest.raises(SpecViolationError):
            read_string(malformed, "kvn", "ocm")
