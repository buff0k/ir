from unittest.mock import patch

import frappe
from frappe.utils import getdate

from ir.ir_coida.doctype.coida_annual_return.coida_annual_return import COIDAAnnualReturn
from ir.tests.compat import UnitTestCase


class TestCOIDAAnnualReturn(UnitTestCase):
	def test_non_march_fiscal_year_is_rejected_for_coida_return(self):
		doc = frappe.new_doc("COIDA Annual Return")
		doc.fiscal_year = "Calendar 2026"
		calendar_year = frappe._dict(year_start_date="2026-01-01", year_end_date="2026-12-31")
		with (
			patch("frappe.get_cached_doc", return_value=calendar_year),
			self.assertRaises(frappe.ValidationError),
		):
			COIDAAnnualReturn.set_and_validate_assessment_period(doc)

	def test_coida_annual_return_calculates_assessment_fee_and_aligns_fiscal_dates(self):
		doc = frappe.new_doc("COIDA Annual Return")
		doc.company = "Test Company"
		doc.industry_class = "Class 1"
		doc.fiscal_year = "2026-2027"
		doc.from_date = "2026-01-01"
		doc.to_date = "2026-12-31"
		doc.total_annual_earnings = 1_250_000

		fiscal_year = frappe._dict(year_start_date="2026-03-01", year_end_date="2027-02-28")
		with (
			patch("frappe.get_cached_doc", return_value=fiscal_year),
			patch(
				"ir.ir_coida.doctype.coida_annual_return.coida_annual_return.get_company_industry_rate",
				return_value=1.35,
			),
		):
			COIDAAnnualReturn.validate(doc)

		self.assertEqual(getdate(fiscal_year.year_start_date), doc.from_date)
		self.assertEqual(getdate(fiscal_year.year_end_date), doc.to_date)
		self.assertEqual(16_875, doc.assessment_fee)
