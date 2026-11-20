from datetime import date

from ir.ir_payroll.doctype.fringe_benefit.fringe_benefit import _assessment_year_end
from ir.ir_payroll.fringe_benefits.tasks import _status_for_dates
from ir.tests.compat import UnitTestCase


class TestFringeBenefit(UnitTestCase):
	def test_status_and_open_ended_assessment_year_are_date_derived(self):
		current = date(2026, 8, 1)
		self.assertEqual("Pending", _status_for_dates("2026-09-01", None, current))
		self.assertEqual("Active", _status_for_dates("2026-03-01", None, current))
		self.assertEqual("Expired", _status_for_dates("2026-03-01", "2026-07-31", current))
		self.assertEqual(date(2027, 2, 28), _assessment_year_end(current))
