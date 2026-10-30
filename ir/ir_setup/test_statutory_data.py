import json
from pathlib import Path

from za_local.tests.compat import UnitTestCase

DATA_DIR = Path(__file__).resolve().parent / "data"


class TestStatutoryData(UnitTestCase):
	def test_public_holiday_fixtures_match_official_2025_to_2027_dates(self):
		expected = {
			2025: {"2025-04-18", "2025-04-21", "2025-04-27", "2025-04-28"},
			2026: {"2026-04-03", "2026-04-06", "2026-08-09", "2026-08-10", "2026-12-26"},
			2027: {"2027-03-21", "2027-03-22", "2027-03-26", "2027-03-29", "2027-12-27"},
		}
		actual_dates = {}
		for year, required_dates in expected.items():
			data = json.loads((DATA_DIR / f"holiday_list_{year}.json").read_text())[0]
			dates = {row["holiday_date"] for row in data["holidays"]}
			actual_dates[year] = dates
			self.assertEqual(data["total_holidays"], len(data["holidays"]))
			self.assertTrue(required_dates.issubset(dates), required_dates - dates)
		self.assertNotIn("2026-12-28", actual_dates[2026])
