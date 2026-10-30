from unittest.mock import patch

import frappe

from ir.ir_labour.report.eea2_income_differentials.eea2_income_differentials import (
	get_data as get_eea2_data,
)
from ir.ir_labour.report_utils import get_permitted_company
from za_local.tests.compat import UnitTestCase


class TestLabourReports(UnitTestCase):
	def test_report_requires_a_permitted_company(self):
		with self.assertRaises(frappe.ValidationError):
			get_permitted_company({})

		with patch("frappe.has_permission", return_value=True) as has_permission:
			self.assertEqual("Test Company", get_permitted_company({"company": "Test Company"}))
		has_permission.assert_called_once_with("Company", "read", "Test Company", throw=True)

	def test_eea2_query_joins_only_latest_salary_assignment(self):
		with (
			patch(
				"ir.ir_labour.report.eea2_income_differentials.eea2_income_differentials.get_permitted_company",
				return_value="Test Company",
			),
			patch(
				"ir.ir_labour.report.eea2_income_differentials.eea2_income_differentials.validate_employee_fields"
			),
			patch("frappe.db.sql", return_value=[]) as sql,
		):
			get_eea2_data({"company": "Test Company"})

		query = sql.call_args.args[0]
		self.assertIn("SELECT latest.name", query)
		self.assertIn("ORDER BY latest.from_date DESC", query)
		self.assertIn("LIMIT 1", query)
