"""
Epoch parsing tests - CCSDS date formats, time tags, TimeScaledEpoch comparisons.

Module under test: src/ccsds_data_messages/models/_epoch.py

All tests cite §7.5.10: "times shall be given in one of the following two formats:
YYYY-MM-DDThh:mm:ss[.d→d][Z]  or  YYYY-DDDThh:mm:ss[.d→d][Z]"
"""

from __future__ import annotations

import pytest

from ccsds_data_messages.models._epoch import (
    TimeScaledEpoch,
    parse_ccsds_epoch,
    validate_ccsds_date,
    validate_time_tag,
)
from ccsds_data_messages.models.values import TimeSystem

# ---------------------------------------------------------------------------
# validate_ccsds_date - accepts calendar and DOY; rejects JD, invalid dates
# ---------------------------------------------------------------------------


class TestValidateCcsdsDate:
    def test_calendar_format_valid_returns_value(self):
        # §7.5.10: YYYY-MM-DDThh:mm:ss is the primary calendar format
        result = validate_ccsds_date("2021-03-15T12:00:00", "epoch")
        assert result == "2021-03-15T12:00:00"

    def test_calendar_format_with_subseconds_valid(self):
        # §7.5.10: "as many 'd' characters as required"
        result = validate_ccsds_date("2021-03-15T12:00:00.123456", "epoch")
        assert result == "2021-03-15T12:00:00.123456"

    def test_calendar_format_with_z_suffix_valid(self):
        # §7.5.10: Z is the optional UTC designator
        result = validate_ccsds_date("2021-03-15T12:00:00Z", "epoch")
        assert result == "2021-03-15T12:00:00Z"

    def test_doy_format_valid_returns_value(self):
        # §7.5.10: YYYY-DDDThh:mm:ss is the DOY format; DOY 74 of 2021 = March 15
        result = validate_ccsds_date("2021-074T12:00:00", "epoch")
        assert result == "2021-074T12:00:00"

    def test_doy_format_day_001_valid(self):
        # Minimum DOY is 001
        result = validate_ccsds_date("2021-001T00:00:00", "epoch")
        assert result == "2021-001T00:00:00"

    def test_doy_format_day_365_non_leap_year_valid(self):
        # 2021 is not a leap year; DOY 365 is valid
        result = validate_ccsds_date("2021-365T00:00:00", "epoch")
        assert result == "2021-365T00:00:00"

    def test_doy_format_day_366_leap_year_valid(self):
        # 2020 is a leap year; DOY 366 is valid
        result = validate_ccsds_date("2020-366T00:00:00", "epoch")
        assert result == "2020-366T00:00:00"

    def test_doy_format_day_366_non_leap_year_raises(self):
        # 2021 is not a leap year; DOY 366 is invalid
        with pytest.raises(ValueError):
            validate_ccsds_date("2021-366T00:00:00", "epoch")

    def test_doy_format_day_400_raises(self):
        # DOY > 366 is never valid
        with pytest.raises(ValueError):
            validate_ccsds_date("2021-400T00:00:00", "epoch")

    def test_doy_format_day_000_raises(self):
        # DOY starts at 001; 000 is never valid
        with pytest.raises(ValueError):
            validate_ccsds_date("2021-000T00:00:00", "epoch")

    def test_calendar_invalid_month_13_raises(self):
        # Calendar month 13 does not exist
        with pytest.raises(ValueError):
            validate_ccsds_date("2021-13-01T00:00:00", "epoch")

    def test_calendar_invalid_day_32_raises(self):
        # March has 31 days; day 32 is invalid
        with pytest.raises(ValueError):
            validate_ccsds_date("2021-03-32T00:00:00", "epoch")

    def test_calendar_feb_29_non_leap_year_raises(self):
        # 2021 is not a leap year; February 29 does not exist
        with pytest.raises(ValueError):
            validate_ccsds_date("2021-02-29T00:00:00", "epoch")

    def test_calendar_feb_29_leap_year_valid(self):
        # 2020 is a leap year; February 29 exists
        result = validate_ccsds_date("2020-02-29T00:00:00", "epoch")
        assert result == "2020-02-29T00:00:00"

    def test_julian_date_like_string_raises(self):
        # A bare decimal isn't one of §7.5.10's two absolute formats, so it's
        # rejected by validate_ccsds_date regardless of what it resembles.
        with pytest.raises(ValueError):
            validate_ccsds_date("2459945.5", "epoch")

    def test_totally_invalid_string_raises(self):
        with pytest.raises(ValueError):
            validate_ccsds_date("not-a-date", "epoch")


# ---------------------------------------------------------------------------
# validate_time_tag - accepts absolute CCSDS date or relative seconds (6.2.2.3)
# ---------------------------------------------------------------------------


class TestValidateTimeTag:
    def test_absolute_ccsds_date_accepted(self):
        # Absolute epoch in calendar format is a valid time tag
        result = validate_time_tag("2021-03-15T12:00:00", "time_tag")
        assert result == "2021-03-15T12:00:00"

    def test_relative_seconds_accepted(self):
        # Numeric-only value is a relative time tag (e.g., in OCM data blocks)
        result = validate_time_tag("86400.0", "time_tag")
        assert result == "86400.0"

    def test_relative_seconds_integer_accepted(self):
        result = validate_time_tag("0.0", "time_tag")
        assert result == "0.0"

    def test_seven_digit_relative_time_accepted(self):
        # A relative time tag with a 7-digit integer part (e.g. ~11.6-115.7
        # days after EPOCH_TZERO) is a valid signed decimal per §6.2.2.3;
        # nothing in the spec restricts its digit count.
        result = validate_time_tag("2459945.5", "time_tag")
        assert result == "2459945.5"


# ---------------------------------------------------------------------------
# parse_ccsds_epoch - returns TimeScaledEpoch
# ---------------------------------------------------------------------------


class TestParseCcsdsEpoch:
    def test_calendar_format_returns_time_scaled_epoch(self):
        epoch = parse_ccsds_epoch("2021-03-15T12:00:00")
        assert isinstance(epoch, TimeScaledEpoch)
        assert epoch.datetime.year == 2021
        assert epoch.datetime.month == 3
        assert epoch.datetime.day == 15
        assert epoch.datetime.hour == 12

    def test_doy_format_equivalent_to_calendar(self):
        # DOY 74 of 2021 = March 15
        epoch_doy = parse_ccsds_epoch("2021-074T00:00:00")
        epoch_cal = parse_ccsds_epoch("2021-03-15T00:00:00")
        assert epoch_doy.datetime == epoch_cal.datetime

    def test_explicit_time_system_preserved(self):
        # The time system is stored alongside the datetime
        epoch = parse_ccsds_epoch("2021-03-15T12:00:00", time_system=TimeSystem.GPS)
        assert epoch.time_system == TimeSystem.GPS

    def test_default_time_system_is_utc(self):
        epoch = parse_ccsds_epoch("2021-03-15T12:00:00")
        assert epoch.time_system == TimeSystem.UTC

    def test_subseconds_preserved(self):
        epoch = parse_ccsds_epoch("2021-03-15T12:00:00.123456")
        assert epoch.datetime.microsecond == 123456

    def test_z_suffix_accepted(self):
        epoch = parse_ccsds_epoch("2021-03-15T12:00:00Z")
        assert epoch.datetime.year == 2021

    def test_totally_invalid_string_raises(self):
        # parse_ccsds_epoch has its own range-checking, reachable by any caller
        # that doesn't pre-validate via validate_ccsds_date - mirrors
        # TestValidateCcsdsDate's rejection matrix, calling parse_ccsds_epoch directly.
        with pytest.raises(ValueError):
            parse_ccsds_epoch("not-a-date")

    def test_doy_day_400_raises(self):
        # DOY > 366 is never valid
        with pytest.raises(ValueError):
            parse_ccsds_epoch("2021-400T00:00:00")

    def test_doy_day_366_non_leap_year_raises(self):
        # 2021 is not a leap year; DOY 366 is invalid
        with pytest.raises(ValueError):
            parse_ccsds_epoch("2021-366T00:00:00")

    def test_julian_date_like_string_raises(self):
        # A bare decimal isn't one of §7.5.10's two absolute formats, so
        # fromisoformat() rejects it regardless of what it resembles.
        with pytest.raises(ValueError):
            parse_ccsds_epoch("2459945.5")

    def test_calendar_invalid_month_13_raises(self):
        with pytest.raises(ValueError):
            parse_ccsds_epoch("2021-13-01T00:00:00")


# ---------------------------------------------------------------------------
# TimeScaledEpoch - same-system ordering; cross-system comparison raises
# ---------------------------------------------------------------------------


class TestTimeScaledEpoch:
    def _utc(self, year: int, month: int = 1, day: int = 1) -> TimeScaledEpoch:
        return parse_ccsds_epoch(
            f"{year}-{month:02d}-{day:02d}T00:00:00", time_system=TimeSystem.UTC
        )

    def _gps(self, year: int, month: int = 1, day: int = 1) -> TimeScaledEpoch:
        return parse_ccsds_epoch(
            f"{year}-{month:02d}-{day:02d}T00:00:00", time_system=TimeSystem.GPS
        )

    def test_same_time_system_lt_comparison_works(self):
        # UTC 2020 < UTC 2021 - safe because same scale
        assert self._utc(2020) < self._utc(2021)

    def test_same_time_system_gt_comparison_works(self):
        assert self._utc(2021) > self._utc(2020)

    def test_same_time_system_le_works(self):
        a = self._utc(2020)
        b = self._utc(2020)
        assert a <= b

    def test_same_time_system_ge_works(self):
        a = self._utc(2020)
        b = self._utc(2020)
        assert a >= b

    def test_cross_time_system_lt_raises(self):
        # UTC < GPS raises: GPS leads UTC by ~18 s; silent comparison would be wrong
        with pytest.raises(ValueError):
            _ = self._utc(2020) < self._gps(2020)

    def test_cross_time_system_le_raises(self):
        with pytest.raises(ValueError):
            _ = self._utc(2020) <= self._gps(2020)

    def test_cross_time_system_gt_raises(self):
        with pytest.raises(ValueError):
            _ = self._utc(2020) > self._gps(2020)

    def test_cross_time_system_ge_raises(self):
        with pytest.raises(ValueError):
            _ = self._utc(2020) >= self._gps(2020)
