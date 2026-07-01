"""
IO utility tests - format_value, format_ccsds_epoch, build_keyword_map, map_kvs.

Module under test: src/ccsds_data_messages/io/_utils.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from ccsds_data_messages.io._utils import (
    build_keyword_map,
    format_ccsds_epoch,
    format_value,
    map_kvs,
)
from ccsds_data_messages.models.opm import OPM
from ccsds_data_messages.models.values import RefFrame, TimeSystem

# ---------------------------------------------------------------------------
# format_value
# ---------------------------------------------------------------------------


class TestFormatValue:
    def test_float_with_format_spec_applied(self):
        # Writers apply FieldMetadata.format_spec to float fields
        result = format_value(6503.514, ".3f")
        assert result == "6503.514"

    def test_float_with_signed_format_spec(self):
        result = format_value(6503.514, "+.3f")
        assert result == "+6503.514"

    def test_float_fallback_uses_g_format(self):
        # Without a spec, floats use ".15g" - never produces "None" or raises
        result = format_value(6503.514, None)
        assert "6503" in result
        assert "None" not in result

    def test_float_zero_formatted_correctly(self):
        result = format_value(0.0, None)
        assert "0" in result

    def test_enum_serialized_as_value_string(self):
        # Enum.value is the spec-defined string (e.g., "EME2000"), not repr
        result = format_value(RefFrame.EME2000)
        assert result == "EME2000"
        assert "RefFrame" not in result

    def test_enum_time_system_serialized_as_value(self):
        result = format_value(TimeSystem.UTC)
        assert result == "UTC"

    def test_integer_formatted_correctly(self):
        # §7.5.4: integers are decimal digits, no decimal point
        result = format_value(42)
        assert result == "42"
        assert "." not in result

    def test_string_value_passes_through(self):
        result = format_value("GCRF")
        assert result == "GCRF"


# ---------------------------------------------------------------------------
# format_ccsds_epoch
# ---------------------------------------------------------------------------


class TestFormatCcsdsEpoch:
    def test_utc_datetime_formatted_as_calendar_string(self):
        # §7.5.10: calendar format YYYY-MM-DDThh:mm:ss[Z]
        dt = datetime(2021, 3, 15, 12, 0, 0, tzinfo=UTC)
        result = format_ccsds_epoch(dt)
        assert result == "2021-03-15T12:00:00Z"

    def test_subseconds_trailing_zeros_stripped(self):
        # §7.5.10: fractional seconds are optional trailing digits (no trailing zeros)
        dt = datetime(2021, 3, 15, 12, 0, 0, 100000, tzinfo=UTC)
        result = format_ccsds_epoch(dt)
        assert result == "2021-03-15T12:00:00.1Z"

    def test_subseconds_non_round_value(self):
        dt = datetime(2021, 3, 15, 12, 0, 0, 123456, tzinfo=UTC)
        result = format_ccsds_epoch(dt)
        assert result == "2021-03-15T12:00:00.123456Z"

    def test_include_z_false_omits_z_suffix(self):
        dt = datetime(2021, 3, 15, 12, 0, 0, tzinfo=UTC)
        result = format_ccsds_epoch(dt, include_z=False)
        assert result == "2021-03-15T12:00:00"
        assert not result.endswith("Z")

    def test_no_subseconds_when_zero_microseconds(self):
        dt = datetime(2021, 3, 15, 12, 30, 45, 0, tzinfo=UTC)
        result = format_ccsds_epoch(dt)
        assert result == "2021-03-15T12:30:45Z"
        assert "." not in result


# ---------------------------------------------------------------------------
# build_keyword_map
# ---------------------------------------------------------------------------


class TestBuildKeywordMap:
    def test_returns_keyword_to_field_mapping_for_opm_metadata(self):
        # Readers use this to route parsed KV pairs to pydantic fields
        kw_map = build_keyword_map(OPM.Metadata)
        assert "OBJECT_NAME" in kw_map
        assert kw_map["OBJECT_NAME"] == "object_name"
        assert "CENTER_NAME" in kw_map
        assert kw_map["CENTER_NAME"] == "center_name"
        assert "REF_FRAME" in kw_map
        assert kw_map["REF_FRAME"] == "ref_frame"
        assert "TIME_SYSTEM" in kw_map
        assert kw_map["TIME_SYSTEM"] == "time_system"

    def test_returns_keyword_to_field_mapping_for_opm_state_vector(self):
        kw_map = build_keyword_map(OPM.Data.StateVector)
        assert "X" in kw_map
        assert kw_map["X"] == "x"
        assert "EPOCH" in kw_map

    def test_does_not_include_unannotated_fields(self):
        # model_config and ClassVar fields must not appear in the keyword map
        kw_map = build_keyword_map(OPM.Header)
        assert "model_config" not in kw_map


# ---------------------------------------------------------------------------
# map_kvs
# ---------------------------------------------------------------------------


class TestMapKvs:
    def test_basic_keyword_mapped_to_field_name(self):
        kvs = {"OBJECT_NAME": "SAT-1", "OBJECT_ID": "2020-001A"}
        result = map_kvs(kvs, [], OPM.Metadata)
        assert result.get("object_name") == "SAT-1"
        assert result.get("object_id") == "2020-001A"

    def test_user_defined_keys_aggregated(self):
        # USER_DEFINED_x keys must be collected under "user_defined" dict with suffix x
        kvs = {"USER_DEFINED_EARTH_MODEL": "EGM96", "USER_DEFINED_CATEGORY": "A"}
        result = map_kvs(kvs, [], OPM.Data.UserDefinedParameters)
        assert "user_defined" in result
        assert result["user_defined"]["EARTH_MODEL"] == "EGM96"
        assert result["user_defined"]["CATEGORY"] == "A"

    def test_comment_injected_from_comments_list(self):
        # Non-empty comments list -> {"comment": [...]} in output
        result = map_kvs({}, ["Line one", "Line two"], OPM.Header)
        assert result.get("comment") == ["Line one", "Line two"]

    def test_empty_comments_list_not_injected(self):
        # Empty comments list must not inject "comment" key (would trigger empty-list validation error)
        result = map_kvs({}, [], OPM.Header)
        assert "comment" not in result

    def test_unknown_keyword_silently_skipped(self):
        # §7.9.2: unknown keywords should not cause parse failure (forward compat)
        kvs = {"TOTALLY_UNKNOWN_KEY": "some_value"}
        result = map_kvs(kvs, [], OPM.Metadata)
        assert "totally_unknown_key" not in result
        # No exception raised
