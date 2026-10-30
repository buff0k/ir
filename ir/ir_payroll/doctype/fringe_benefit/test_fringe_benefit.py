import json
from datetime import date
from pathlib import Path

from ir.ir_payroll.doctype.fringe_benefit.fringe_benefit import _assessment_year_end
from ir.ir_payroll.fringe_benefits.tasks import _status_for_dates
from za_local.tests.compat import UnitTestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


class TestFringeBenefit(UnitTestCase):
	def test_status_and_open_ended_assessment_year_are_date_derived(self):
		current = date(2026, 8, 1)
		self.assertEqual("Pending", _status_for_dates("2026-09-01", None, current))
		self.assertEqual("Active", _status_for_dates("2026-03-01", None, current))
		self.assertEqual("Expired", _status_for_dates("2026-03-01", "2026-07-31", current))
		self.assertEqual(date(2027, 2, 28), _assessment_year_end(current))

	def test_salary_component_fixtures_are_non_cash_taxable_and_correctly_mapped(self):
		# This data used to live in za_local's own sa_setup/data/salary_components.json
		# plus a DEFAULT_SALARY_COMPONENT_SARS_CODES/DEFAULT_IRP5_EXCLUDED_SALARY_
		# COMPONENTS dict in install.py. Both were superseded by ir's own fixture
		# (ir/ir/fixtures/salary_component.json), which carries the SARS code and
		# IRP5-exclusion flag directly on each component's own fields instead.
		path = PACKAGE_ROOT / "fixtures" / "salary_component.json"
		components = {row["name"]: row for row in json.loads(path.read_text())}
		for name in (
			"Company Car Benefit",
			"Company Car PAYE Adjustment",
			"Housing Fringe Benefit",
			"Low Interest Loan Fringe Benefit",
			"Other Fringe Benefit",
		):
			self.assertEqual(1, components[name]["is_tax_applicable"])
			self.assertEqual(1, components[name]["do_not_include_in_total"])
			self.assertEqual(1, components[name]["do_not_include_in_accounts"])

		self.assertEqual("3802", components["Company Car Benefit"]["za_sars_payroll_code"])
		self.assertEqual("3805", components["Housing Fringe Benefit"]["za_sars_payroll_code"])
		self.assertEqual("3801", components["Low Interest Loan Fringe Benefit"]["za_sars_payroll_code"])
		self.assertEqual(1, components["Company Car PAYE Adjustment"]["za_exclude_from_irp5"])
