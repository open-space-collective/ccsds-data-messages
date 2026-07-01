"""
Registry tests — get_reader, get_writer, register_reader, register_writer, error paths.

Module under test: src/ccsds_data_messages/io/registry.py
"""

from __future__ import annotations

import pytest

from ccsds_data_messages.exceptions import UnsupportedAdapterError
from ccsds_data_messages.io.registry import (
    get_reader,
    get_writer,
    register_reader,
    register_writer,
)


def _is_reader(obj) -> bool:
    return hasattr(obj, "read") and hasattr(obj, "read_string")


def _is_writer(obj) -> bool:
    return hasattr(obj, "write") and hasattr(obj, "write_string")


# ---------------------------------------------------------------------------
# get_reader — all built-in (format, message_type) pairs
# ---------------------------------------------------------------------------


class TestGetReader:
    def test_kvn_opm_returns_reader_port(self):
        reader = get_reader("kvn", "opm")
        assert _is_reader(reader)

    def test_kvn_omm_returns_reader_port(self):
        reader = get_reader("kvn", "omm")
        assert _is_reader(reader)

    def test_kvn_oem_returns_reader_port(self):
        reader = get_reader("kvn", "oem")
        assert _is_reader(reader)

    def test_kvn_ocm_returns_reader_port(self):
        reader = get_reader("kvn", "ocm")
        assert _is_reader(reader)

    def test_xml_opm_returns_reader_port(self):
        reader = get_reader("xml", "opm")
        assert _is_reader(reader)

    def test_xml_oem_returns_reader_port(self):
        reader = get_reader("xml", "oem")
        assert _is_reader(reader)

    def test_xml_omm_returns_reader_port(self):
        reader = get_reader("xml", "omm")
        assert _is_reader(reader)

    def test_unregistered_pair_raises_unsupported_adapter_error(self):
        # Callers need a typed error, not KeyError or AttributeError
        with pytest.raises(UnsupportedAdapterError):
            get_reader("kvn", "xyz_unknown_type")

    def test_unregistered_format_raises_unsupported_adapter_error(self):
        with pytest.raises(UnsupportedAdapterError):
            get_reader("csv", "opm")

    def test_string_format_uppercase_normalized(self):
        # "KVN" should work the same as "kvn"
        reader = get_reader("KVN", "OPM")
        assert _is_reader(reader)

    def test_string_type_mixed_case_normalized(self):
        reader = get_reader("KVN", "Opm")
        assert _is_reader(reader)

    def test_same_key_returns_same_instance(self):
        # Registry caches singleton instances
        a = get_reader("kvn", "opm")
        b = get_reader("kvn", "opm")
        assert a is b


# ---------------------------------------------------------------------------
# get_writer — all built-in (format, message_type) pairs
# ---------------------------------------------------------------------------


class TestGetWriter:
    def test_kvn_opm_returns_writer_port(self):
        writer = get_writer("kvn", "opm")
        assert _is_writer(writer)

    def test_kvn_omm_returns_writer_port(self):
        writer = get_writer("kvn", "omm")
        assert _is_writer(writer)

    def test_kvn_oem_returns_writer_port(self):
        writer = get_writer("kvn", "oem")
        assert _is_writer(writer)

    def test_kvn_ocm_returns_writer_port(self):
        writer = get_writer("kvn", "ocm")
        assert _is_writer(writer)

    def test_xml_opm_returns_writer_port(self):
        writer = get_writer("xml", "opm")
        assert _is_writer(writer)

    def test_xml_oem_returns_writer_port(self):
        writer = get_writer("xml", "oem")
        assert _is_writer(writer)

    def test_unregistered_pair_raises_unsupported_adapter_error(self):
        with pytest.raises(UnsupportedAdapterError):
            get_writer("kvn", "xyz_unknown_type")

    def test_unregistered_format_raises_unsupported_adapter_error(self):
        with pytest.raises(UnsupportedAdapterError):
            get_writer("json", "opm")


# ---------------------------------------------------------------------------
# register_reader / register_writer — extensibility contract
# ---------------------------------------------------------------------------


class TestRegisterAdapter:
    def test_register_reader_replaces_adapter(self):
        """After register_reader, get_reader returns the new adapter."""
        original = get_reader("kvn", "opm")

        class _StubReader:
            def read(self, source):
                raise NotImplementedError

            def read_string(self, content):
                raise NotImplementedError

        try:
            register_reader("kvn", "opm", _StubReader)
            result = get_reader("kvn", "opm")
            assert isinstance(result, _StubReader)
        finally:
            # Restore original so other tests are not affected
            register_reader("kvn", "opm", type(original))

    def test_register_writer_replaces_adapter(self):
        """After register_writer, get_writer returns the new adapter."""
        original = get_writer("kvn", "opm")

        class _StubWriter:
            def write(self, model, destination, options=None):
                raise NotImplementedError

            def write_string(self, model, options=None):
                raise NotImplementedError

        try:
            register_writer("kvn", "opm", _StubWriter)
            result = get_writer("kvn", "opm")
            assert isinstance(result, _StubWriter)
        finally:
            # Restore original
            register_writer("kvn", "opm", type(original))

    def test_register_reader_clears_cache(self):
        """Registering a new adapter invalidates the singleton cache."""
        before = get_reader("kvn", "omm")

        class _StubReader:
            def read(self, source):
                raise NotImplementedError

            def read_string(self, content):
                raise NotImplementedError

        try:
            register_reader("kvn", "omm", _StubReader)
            after = get_reader("kvn", "omm")
            # After registration, the cached instance should be fresh (not the old one)
            assert isinstance(after, _StubReader)
        finally:
            register_reader("kvn", "omm", type(before))
