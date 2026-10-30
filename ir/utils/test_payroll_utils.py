from unittest.mock import patch

import frappe

from ir.utils import payroll_utils
from za_local.tests.compat import UnitTestCase


class TestAdditionalSalarySelection(UnitTestCase):
	@patch.object(payroll_utils.frappe, "get_all")
	@patch.object(payroll_utils, "hrms_get_additional_salaries")
	def test_regular_additional_salary_preserves_hrms_aliases(self, get_hrms_salaries, get_all):
		selected = frappe._dict(
			name="AS-REC-1",
			component="Recurring Allowance",
			amount=1500,
			is_recurring=1,
			overwrite=1,
			ref_doctype="Employee Benefit Claim",
		)
		get_hrms_salaries.return_value = [selected]
		get_all.return_value = [
			frappe._dict(
				name=selected.name,
				za_is_company_contribution=0,
				ref_docname="EBC-0001",
			)
		]

		result = payroll_utils.get_additional_salaries("EMP-1", "2026-03-01", "2026-03-31", "earnings")

		self.assertEqual(result, [selected])
		self.assertEqual(result[0].component, "Recurring Allowance")
		self.assertEqual(result[0].overwrite, 1)
		self.assertEqual(result[0].ref_docname, "EBC-0001")
		get_hrms_salaries.assert_called_once_with("EMP-1", "2026-03-01", "2026-03-31", "earnings")

	@patch.object(payroll_utils.frappe, "get_all")
	@patch.object(payroll_utils, "hrms_get_additional_salaries")
	def test_company_contributions_are_partitioned_from_both_hrms_types(self, get_hrms_salaries, get_all):
		earning = frappe._dict(name="AS-EARN", component="UIF Employer")
		deduction = frappe._dict(name="AS-DED", component="SDL Employer")
		get_hrms_salaries.side_effect = [[earning], [deduction]]
		get_all.return_value = [
			frappe._dict(name="AS-EARN", za_is_company_contribution=1, ref_docname=None),
			frappe._dict(name="AS-DED", za_is_company_contribution=0, ref_docname=None),
		]

		result = payroll_utils.get_additional_salaries(
			"EMP-1", "2026-03-01", "2026-03-31", "company_contributions"
		)

		self.assertEqual(result, [earning])
		self.assertEqual(get_hrms_salaries.call_count, 2)
