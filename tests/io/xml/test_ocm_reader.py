"""
Unit tests for the XML OCM reader adapter.

Instantiates ``XMLOCMReader`` directly (as opposed to the high-level
``read()`` dispatch tested in ``tests/io/test_reader.py``) and exercises
``read()`` / ``read_string()``. Valid OCM/XML input is produced by the paired
``XMLOCMWriter`` and read back; the ``ocm_g20.xml`` spec fixture is also
referenced to document a known reader gap.

Module under test:
  src/ccsds_data_messages/io/xml/ocm_reader.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import FIXTURES
from conftest import make_ocm
from conftest import make_ocm_with_trajectory

from ccsds_data_messages import OCM
from ccsds_data_messages.io.xml.ocm_reader import XMLOCMReader
from ccsds_data_messages.io.xml.ocm_writer import XMLOCMWriter

if TYPE_CHECKING:
    from pathlib import Path


class TestXMLOCMReader:
    def test_read_string_returns_ocm_instance(self):
        model = make_ocm()
        content = XMLOCMWriter().write_string(model)
        msg = XMLOCMReader().read_string(content)
        assert isinstance(msg, OCM)

    def test_read_string_populates_stable_fields(self):
        model = make_ocm(metadata={"object_name": "TESTSAT"})
        content = XMLOCMWriter().write_string(model)
        msg = XMLOCMReader().read_string(content)
        assert msg.header.originator == "JAXA"
        assert msg.metadata.object_name == "TESTSAT"
        assert str(msg.metadata.time_system) == "UTC"
        assert msg.metadata.epoch_tzero == model.metadata.epoch_tzero

    def test_read_parses_trajectory_state_history(self):
        model = make_ocm_with_trajectory()
        content = XMLOCMWriter().write_string(model)
        msg = XMLOCMReader().read_string(content)
        assert msg.trajectory_states is not None
        assert len(msg.trajectory_states) == 1
        traj = msg.trajectory_states[0]
        assert str(traj.traj_type) == "CARTPV"
        assert len(traj.data_lines) == 2

    def test_read_matches_read_string(self, tmp_path: Path):
        """read() from a file agrees with read_string() on identical content."""
        model = make_ocm_with_trajectory()
        content = XMLOCMWriter().write_string(model)
        path = tmp_path / "in.xml"
        path.write_text(content, encoding="utf-8")

        from_path = XMLOCMReader().read(path)
        from_string = XMLOCMReader().read_string(content)
        assert from_path.model_dump() == from_string.model_dump()

    def test_read_spec_fixture_g20(self):
        """The g20 spec fixture parses, including its <USER_DEFINED parameter=...> block."""
        msg = XMLOCMReader().read(FIXTURES / "ocm_g20.xml")
        assert isinstance(msg, OCM)
        # Section : user-defined entries carry their key in the ``parameter`` attribute.
        assert msg.user_defined is not None
        assert msg.user_defined.user_defined == {
            "CONSOLE_POC": "MAXWELL RAFERTY",
            "EARTH_MODEL": "WGS-84",
        }
