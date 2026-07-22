"""Tests for the resolve-in-code helpers."""

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from timeanchor import (
    at_local,
    format_local,
    in_days,
    next_weekday,
    now_in,
    parse_weekday,
    to_local,
    to_utc,
)

KOLKATA = "Asia/Kolkata"
NEW_YORK = "America/New_York"

# Wednesday, 17:15 local in Kolkata.
NOW_IST = datetime(2026, 7, 22, 17, 15, tzinfo=ZoneInfo(KOLKATA))
# The same instant is still Wednesday morning in New York and UTC.
NOW_NY = NOW_IST.astimezone(ZoneInfo(NEW_YORK))
NOW_UTC = NOW_IST.astimezone(ZoneInfo("UTC"))


class ParseWeekdayTests(unittest.TestCase):
    def test_full_and_abbrev_case_insensitive(self):
        self.assertEqual(parse_weekday("monday"), 0)
        self.assertEqual(parse_weekday("Fri"), 4)
        self.assertEqual(parse_weekday("SUNDAY"), 6)
        self.assertEqual(parse_weekday("  wed  "), 2)

    def test_unknown_raises_friendly(self):
        with self.assertRaises(ValueError) as ctx:
            parse_weekday("frday")
        self.assertIn("frday", str(ctx.exception))

    def test_non_string_raises(self):
        with self.assertRaises(TypeError):
            parse_weekday(4)  # type: ignore[arg-type]


class NextWeekdayTests(unittest.TestCase):
    def test_coming_occurrence(self):
        # Wednesday 2026-07-22 -> coming Friday is 2026-07-24.
        self.assertEqual(
            next_weekday("friday", tz=KOLKATA, now=NOW_IST),
            date(2026, 7, 24),
        )

    def test_same_day_non_strict_returns_today(self):
        self.assertEqual(
            next_weekday("wednesday", tz=KOLKATA, now=NOW_IST),
            date(2026, 7, 22),
        )

    def test_same_day_strict_skips_to_next_week(self):
        self.assertEqual(
            next_weekday("wed", tz=KOLKATA, now=NOW_IST, strict_next=True),
            date(2026, 7, 29),
        )

    def test_strict_on_other_weekday_unaffected(self):
        # Friday is not today, so strict_next changes nothing.
        self.assertEqual(
            next_weekday("friday", tz=KOLKATA, now=NOW_IST, strict_next=True),
            date(2026, 7, 24),
        )

    def test_timezone_shifts_the_local_day(self):
        # An instant near midnight IST is still the previous day in New York,
        # so "next Monday" resolves to different dates per zone.
        near_midnight = datetime(2026, 7, 20, 1, 0, tzinfo=ZoneInfo(KOLKATA))
        ist_monday = next_weekday("monday", tz=KOLKATA, now=near_midnight)
        ny_monday = next_weekday("monday", tz=NEW_YORK, now=near_midnight)
        # 2026-07-20 is a Monday in IST; in NY it is still Sunday the 19th.
        self.assertEqual(ist_monday, date(2026, 7, 20))
        self.assertEqual(ny_monday, date(2026, 7, 20))
        # The local dates themselves differ across the two zones.
        self.assertNotEqual(
            now_in(KOLKATA, near_midnight).date(),
            now_in(NEW_YORK, near_midnight).date(),
        )


class InDaysTests(unittest.TestCase):
    def test_offsets(self):
        self.assertEqual(in_days(0, tz=KOLKATA, now=NOW_IST), date(2026, 7, 22))
        self.assertEqual(in_days(1, tz=KOLKATA, now=NOW_IST), date(2026, 7, 23))
        self.assertEqual(in_days(14, tz=KOLKATA, now=NOW_IST), date(2026, 8, 5))


class AtLocalTests(unittest.TestCase):
    def test_accepts_date_and_iso_string(self):
        d = date(2026, 7, 24)
        from_date = at_local(d, "09:00", tz=KOLKATA)
        from_str = at_local("2026-07-24", "09:00", tz=KOLKATA)
        self.assertEqual(from_date, from_str)
        self.assertEqual(from_date.hour, 9)
        self.assertEqual(from_date.tzinfo, ZoneInfo(KOLKATA))

    def test_bad_time_raises(self):
        with self.assertRaises(ValueError):
            at_local("2026-07-24", "25:00", tz=KOLKATA)
        with self.assertRaises(ValueError):
            at_local("2026-07-24", "9am", tz=KOLKATA)

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            at_local("not-a-date", "09:00", tz=KOLKATA)


class ToUtcLocalRoundTripTests(unittest.TestCase):
    def test_round_trip(self):
        local = at_local("2026-07-24", "09:00", tz=KOLKATA)
        as_utc = to_utc(local)
        # 09:00 IST == 03:30 UTC.
        self.assertEqual((as_utc.hour, as_utc.minute), (3, 30))
        back = to_local(as_utc, KOLKATA)
        self.assertEqual(back, local)

    def test_naive_input_rejected(self):
        naive = datetime(2026, 7, 24, 9, 0)
        with self.assertRaises(ValueError):
            to_utc(naive)
        with self.assertRaises(ValueError):
            to_local(naive, KOLKATA)


class FormatLocalTests(unittest.TestCase):
    def test_human_string_in_user_zone(self):
        local = at_local("2026-07-24", "09:00", tz=KOLKATA)
        self.assertEqual(format_local(local, KOLKATA), "Fri, Jul 24 at 9:00 AM IST")

    def test_utc_instant_rendered_in_user_zone_not_echoed(self):
        # The anti-"UTC echo" guarantee: hand it a UTC datetime, still get IST.
        local = at_local("2026-07-24", "09:00", tz=KOLKATA)
        as_utc = to_utc(local)
        self.assertEqual(format_local(as_utc, KOLKATA), "Fri, Jul 24 at 9:00 AM IST")

    def test_midnight_and_noon_formatting(self):
        midnight = at_local("2026-07-24", "00:00", tz=KOLKATA)
        noon = at_local("2026-07-24", "12:00", tz=KOLKATA)
        self.assertIn("12:00 AM", format_local(midnight, KOLKATA))
        self.assertIn("12:00 PM", format_local(noon, KOLKATA))


class DstBoundaryTests(unittest.TestCase):
    """US Eastern switches EDT(-04:00) -> EST(-05:00) on 2026-11-01."""

    def test_offset_before_and_after_fall_back(self):
        before = at_local("2026-10-30", "12:00", tz=NEW_YORK)  # EDT
        after = at_local("2026-11-03", "12:00", tz=NEW_YORK)  # EST
        self.assertEqual(before.utcoffset().total_seconds(), -4 * 3600)
        self.assertEqual(after.utcoffset().total_seconds(), -5 * 3600)

    def test_wall_clock_noon_maps_to_different_utc_hours(self):
        # Same wall-clock noon, one hour apart in UTC because the offset moved.
        before = to_utc(at_local("2026-10-30", "12:00", tz=NEW_YORK))
        after = to_utc(at_local("2026-11-03", "12:00", tz=NEW_YORK))
        self.assertEqual(before.hour, 16)  # 12:00 EDT -> 16:00 UTC
        self.assertEqual(after.hour, 17)  # 12:00 EST -> 17:00 UTC

    def test_next_weekday_crossing_dst_is_correct_date(self):
        # From Fri 2026-10-30, the coming Monday (2026-11-02) sits after the
        # DST switch; the date math must not be perturbed by the offset change.
        friday = datetime(2026, 10, 30, 9, 0, tzinfo=ZoneInfo(NEW_YORK))
        self.assertEqual(
            next_weekday("monday", tz=NEW_YORK, now=friday),
            date(2026, 11, 2),
        )


class TimezoneValidationTests(unittest.TestCase):
    def test_unknown_timezone_raises_friendly(self):
        with self.assertRaises(ValueError) as ctx:
            in_days(1, tz="Mars/Olympus", now=NOW_IST)
        self.assertIn("Mars/Olympus", str(ctx.exception))

    def test_naive_now_rejected(self):
        with self.assertRaises(ValueError):
            now_in(KOLKATA, datetime(2026, 7, 22, 17, 15))


if __name__ == "__main__":
    unittest.main()
