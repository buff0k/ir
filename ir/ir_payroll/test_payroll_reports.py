from unittest.mock import patch

import frappe

from ir.ir_payroll.report.emp201_report.emp201_report import get_data as get_emp201_report
from ir.ir_payroll.report.retirement_fund_deductions.retirement_fund_deductions import (
	RETIREMENT_FUND_CODES,
	get_data as get_retirement_report,
)
from ir.ir_payroll.report.statutory_submissions_summary.statutory_submissions_summary import (
	get_data as get_statutory_summary,
)
from ir.tests.compat import UnitTestCase


class TestPayrollReports(UnitTestCase):
	def test_reports_filter_submitted_rows_and_deduplicate_eti(self):
		filters = {"company": "_Test Company", "from_date": "2026-03-01", "to_date": "2026-03-31"}
		with patch("frappe.db.sql", return_value=[]) as sql:
			get_emp201_report(filters)
		self.assertIn("docstatus = 1", sql.call_args.args[0])

		with patch("frappe.db.sql", return_value=[]) as sql:
			get_statutory_summary(filters)
		query = sql.call_args.args[0]
		self.assertIn("IFNULL(ss.za_monthly_eti, 0) = 0", query)
		self.assertIn("cc.parenttype = 'Salary Slip'", query)

	def test_retirement_report_uses_only_retirement_sars_codes(self):
		self.assertEqual({"4001", "4003", "4006"}, RETIREMENT_FUND_CODES)
		rows = [
			frappe._dict(salary_slip="SS-1", retirement_taxable_excess=1_000),
			frappe._dict(salary_slip="SS-1", retirement_taxable_excess=1_000),
		]
		with patch("frappe.db.sql", return_value=rows) as sql:
			result = get_retirement_report(frappe._dict(company="_Test Company"))
		query = sql.call_args.args[0]
		self.assertNotIn("LIKE '%%pension%%'", query)
		self.assertIn("parenttype = 'Salary Slip'", query)
		self.assertEqual([1_000, 0], [row.retirement_taxable_excess for row in result])

	def test_retirement_fund_report_returns_empty_without_company_filter(self):
		self.assertEqual([], get_retirement_report(frappe._dict()))

	def test_sa_print_formats_are_registered_for_expected_doctypes(self):
		expected = {
			"SA Sales Invoice": "Sales Invoice",
			"SA Full Tax Invoice": "Sales Invoice",
			"SA Abridged Tax Invoice": "Sales Invoice",
			"SA Credit Note": "Sales Invoice",
			"SA Purchase Invoice": "Purchase Invoice",
			"SA Debit Note": "Purchase Invoice",
			"SA Quotation": "Quotation",
			"SA Sales Order": "Sales Order",
			"SA Delivery Note": "Delivery Note",
			"SA Purchase Order": "Purchase Order",
			"SA Payment Entry": "Payment Entry",
			"SA Salary Slip": "Salary Slip",
			"IRP5 Employee Certificate": "IRP5 Certificate",
			"IRP5-it3 Certificate": "IRP5 Certificate",
		}
		for print_format, doc_type in expected.items():
			record = frappe.db.get_value(
				"Print Format",
				print_format,
				["doc_type", "standard", "disabled"],
				as_dict=True,
			)
			self.assertIsNotNone(record, msg=f"Missing Print Format: {print_format}")
			self.assertEqual(doc_type, record.doc_type)
			self.assertEqual("Yes", record.standard)
			self.assertEqual(0, record.disabled)
