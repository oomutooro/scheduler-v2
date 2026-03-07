from django.test import TestCase
from datetime import date

from core.services import season as season_utils


class SeasonUtilsTest(TestCase):
    def test_summer_and_winter_date_ranges(self):
        # Basic sanity checks: start < end and dates cover expected months
        s_start, s_end = season_utils.get_summer_dates(2026)
        self.assertLess(s_start, s_end)
        self.assertEqual(s_start.month, 3)
        self.assertEqual(s_end.month, 10)  # end is last Saturday of October

        w_start, w_end = season_utils.get_winter_dates(2026)
        self.assertLess(w_start, w_end)
        # Winter starts after last Sat of Oct, which is in Nov; ends in March of next year
        self.assertEqual(w_start.month, 11)
        self.assertEqual(w_end.month, 3)

    def test_get_season_for_date(self):
        # April 1 should be in summer for that year
        self.assertEqual(season_utils.get_season_for_date(date(2026, 4, 1)), ('summer', 2026))
        # November 1 should be in winter for that year
        self.assertEqual(season_utils.get_season_for_date(date(2026, 11, 1)), ('winter', 2026))

    def test_is_date_in_season(self):
        # April 15, 2026 should be inside summer 2026
        self.assertTrue(season_utils.is_date_in_season(date(2026, 4, 15), 'summer', 2026))
        # November 15, 2026 should be inside winter 2026
        self.assertTrue(season_utils.is_date_in_season(date(2026, 11, 15), 'winter', 2026))

