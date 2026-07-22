"""Tests for anchor_block rendering."""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from timeanchor import anchor_block

KOLKATA = "Asia/Kolkata"
NEW_YORK = "America/New_York"

NOW_IST = datetime(2026, 7, 22, 17, 15, tzinfo=ZoneInfo(KOLKATA))


class AnchorBlockTests(unittest.TestCase):
    def setUp(self):
        self.block = anchor_block(tz=KOLKATA, days=14, now=NOW_IST)

    def test_header_has_today_weekday_date_and_offset(self):
        self.assertIn("Today is Wednesday, 2026-07-22.", self.block)
        self.assertIn("Local time: 17:15 (Asia/Kolkata, UTC+05:30).", self.block)

    def test_has_all_sections(self):
        self.assertIn("## Current date & time", self.block)
        self.assertIn(
            "## Date anchors (use these — never derive weekdays yourself)",
            self.block,
        )
        self.assertIn('## "this" vs "next"', self.block)

    def test_table_row_count_matches_days_plus_one(self):
        # Rows look like "<key>...<abbrev> <iso>  (<notes>)"; count the ISO
        # dates in the anchor table region.
        table = self.block.split("## Date anchors")[1].split('## "this"')[0]
        date_rows = [ln for ln in table.splitlines() if "2026-" in ln]
        self.assertEqual(len(date_rows), 15)  # days=14 -> offsets 0..14

    def test_today_tomorrow_labels(self):
        self.assertIn("Today       Wed 2026-07-22", self.block)
        self.assertIn("Tomorrow    Thu 2026-07-23", self.block)

    def test_this_and_next_friday_lines(self):
        self.assertIn("Fri 2026-07-24  (this Friday, in 2 days)", self.block)
        self.assertIn("Fri 2026-07-31  (next Friday, in 9 days)", self.block)

    def test_disambiguation_section_pins_this_next_friday(self):
        self.assertIn("this Friday    = Fri 2026-07-24", self.block)
        self.assertIn("next Friday    = Fri 2026-07-31", self.block)

    def test_this_today_weekday_is_today(self):
        # Today is Wednesday, so "this Wednesday" is today per the convention.
        self.assertIn("this Wednesday = Wed 2026-07-22", self.block)

    def test_custom_day_count(self):
        block = anchor_block(tz=KOLKATA, days=3, now=NOW_IST)
        table = block.split("## Date anchors")[1].split('## "this"')[0]
        date_rows = [ln for ln in table.splitlines() if "2026-" in ln]
        self.assertEqual(len(date_rows), 4)  # offsets 0..3

    def test_days_zero_rejected(self):
        with self.assertRaises(ValueError):
            anchor_block(tz=KOLKATA, days=0, now=NOW_IST)

    def test_default_utc_zone(self):
        # The same instant, rendered in UTC, is still 2026-07-22 (11:45 UTC).
        block = anchor_block(tz="UTC", days=7, now=NOW_IST)
        self.assertIn("Today is Wednesday, 2026-07-22.", block)
        self.assertIn("(UTC, UTC+00:00)", block)

    def test_new_york_zone_offset(self):
        block = anchor_block(tz=NEW_YORK, days=7, now=NOW_IST)
        # 17:15 IST is 07:45 EDT the same day.
        self.assertIn("Local time: 07:45 (America/New_York, UTC-04:00).", block)


class AnchorBlockDeterminismTests(unittest.TestCase):
    def test_same_inputs_same_output(self):
        a = anchor_block(tz=KOLKATA, days=14, now=NOW_IST)
        b = anchor_block(tz=KOLKATA, days=14, now=NOW_IST)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
