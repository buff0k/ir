# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, add_months, getdate, nowdate

from ir.industrial_relations.doctype.retrenchment_process.retrenchment_costing import compute_row_costs
from ir.industrial_relations.doctype.retrenchment_process.retrenchment_process import get_189a_threshold
from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_branch, get_reference_company, get_reference_designation

# On IntegrationTestCase, the doctype test records and all link-field test
# record dependencies are recursively loaded. Use these module variables to
# add/remove to/from that list.
#
# Every one of Retrenchment Process's own Link targets is ignored here - both
# its direct fields (company, and its own self-referencing amended_from) and
# every Link field on its two child tables (Retrenchment Affected Employee:
# branch/designation/employee/outcome/dismissal_form/termination_form/
# transferred_via; Retrenchment Employee Allowance: employee/salary_component)
# - this test builds its own minimal, synthetic fixtures via make_employee()/
# make_retrenchment_process()/get_reference_*() instead of letting Frappe
# recursively auto-generate them, since that walk pulls in erpnext/hrms's own
# legacy test-bootstrap code (BootStrapTestData et al) which assumes a
# pristine site and collides with this site's real Company/Fiscal Year/
# Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Retrenchment Process",
	"Company",
	"Branch",
	"Designation",
	"Employee",
	"Offence Outcome",
	"Dismissal Form",
	"Termination Form",
	"Site Transfer Form",
	"Salary Component",
]


class IntegrationTestRetrenchmentProcess(IRSyntheticDataTestCase):
	"""Functional tests for Retrenchment Process's validation rules (Company
	matching, duplicate/empty Affected Employees, protected-row removal guard),
	the s189A threshold sliding scale, and the costing calculations."""

	# ---- pure-function tests: no DB needed ----------------------------------

	def test_189a_threshold_below_minimum_employer_size_is_none(self):
		self.assertIsNone(get_189a_threshold(50))
		self.assertIsNone(get_189a_threshold(1))

	def test_189a_threshold_tier_boundaries(self):
		self.assertEqual(get_189a_threshold(51), 10)
		self.assertEqual(get_189a_threshold(200), 10)
		self.assertEqual(get_189a_threshold(201), 20)
		self.assertEqual(get_189a_threshold(300), 20)
		self.assertEqual(get_189a_threshold(301), 30)
		self.assertEqual(get_189a_threshold(400), 30)
		self.assertEqual(get_189a_threshold(401), 40)
		self.assertEqual(get_189a_threshold(500), 40)
		self.assertEqual(get_189a_threshold(501), 50)
		self.assertEqual(get_189a_threshold(10000), 50)

	def test_compute_row_costs_worked_example(self):
		notice_date = getdate("2025-01-01")
		row = frappe._dict(
			{
				"s189_notice_date": notice_date,
				"date_of_joining": getdate("2020-01-01"),
				"rate_per_hour": 294.73,
				"hours_per_day": 9,
				"leave_days_projected": 10,
			}
		)
		severance_terms = {
			"severance_weeks_per_completed_year": 1,
			"severance_hours_per_week": 45,
			"minimum_severance_weeks": 0,
		}

		result = compute_row_costs(row, total_allowances=500, severance_terms=severance_terms)

		thirty_days_date = add_days(notice_date, 30)
		self.assertEqual(result["thirty_days_date"], thirty_days_date)
		# 2020-01-01 -> 2025-01-31 is 5 completed years.
		self.assertEqual(result["completed_years"], 5)
		# >= 1 completed year -> 4 weeks' notice.
		self.assertEqual(result["notice_weeks"], 4)
		self.assertEqual(result["notice_ends_date"], add_days(thirty_days_date, 28))

		hours_per_month = 9 * 21.66667
		expected_weekly_rate = (294.73 * hours_per_month + 500) / 4.333
		self.assertAlmostEqual(result["weekly_rate"], expected_weekly_rate, places=2)
		self.assertAlmostEqual(result["estimated_notice_pay"], expected_weekly_rate * 4, places=2)

		# 5 completed years * 1 week/year * 45 hours/week * rate/hour.
		expected_severance = 5 * 1 * 45 * 294.73
		self.assertAlmostEqual(result["estimated_severance_pay"], expected_severance, places=2)

		expected_leave_pay = 294.73 * 9 * 10
		self.assertAlmostEqual(result["estimated_leave_pay"], expected_leave_pay, places=2)

		expected_total = expected_severance + result["estimated_notice_pay"] + expected_leave_pay
		self.assertAlmostEqual(result["estimated_total_cost"], expected_total, places=2)

	def test_compute_row_costs_minimum_severance_weeks_floor(self):
		# 0 completed years of service (joined the same month notice was served)
		# but a negotiated 1-week minimum floor still applies.
		notice_date = getdate(nowdate())
		row = frappe._dict(
			{
				"s189_notice_date": notice_date,
				"date_of_joining": notice_date,
				"rate_per_hour": 100,
				"hours_per_day": 8,
				"leave_days_projected": 0,
			}
		)
		severance_terms = {
			"severance_weeks_per_completed_year": 1,
			"severance_hours_per_week": 45,
			"minimum_severance_weeks": 1,
		}

		result = compute_row_costs(row, total_allowances=0, severance_terms=severance_terms)

		self.assertEqual(result["completed_years"], 0)
		self.assertAlmostEqual(result["estimated_severance_pay"], 1 * 45 * 100, places=2)

	def test_compute_row_costs_no_notice_date_leaves_notice_and_severance_zero(self):
		row = frappe._dict(
			{
				"s189_notice_date": None,
				"date_of_joining": getdate("2020-01-01"),
				"rate_per_hour": 100,
				"hours_per_day": 9,
				"leave_days_projected": 5,
			}
		)
		result = compute_row_costs(
			row,
			total_allowances=0,
			severance_terms={"severance_weeks_per_completed_year": 1, "severance_hours_per_week": 45, "minimum_severance_weeks": 0},
		)

		self.assertEqual(result["notice_weeks"], 0)
		self.assertEqual(result["estimated_notice_pay"], 0.0)
		self.assertEqual(result["estimated_severance_pay"], 0.0)
		# Leave payout is independent of the notice-date branch.
		self.assertAlmostEqual(result["estimated_leave_pay"], 100 * 9 * 5, places=2)

	# ---- DB-backed validation tests -----------------------------------------

	def test_empty_affected_employees_is_blocked(self):
		company = get_reference_company()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Retrenchment Process",
					"process_title": "ZZTEST empty process",
					"company": company,
					"process_type": "Section 189",
					"affected_employees": [],
				}
			).insert(ignore_permissions=True)

	def test_duplicate_employee_in_affected_employees_is_blocked(self):
		employee = self.make_employee()
		branch = get_reference_branch()
		designation = get_reference_designation()

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Retrenchment Process",
					"process_title": "ZZTEST duplicate process",
					"company": employee.company,
					"process_type": "Section 189",
					"affected_employees": [
						{"branch": branch, "designation": designation, "employee": employee.name},
						{"branch": branch, "designation": designation, "employee": employee.name},
					],
				}
			).insert(ignore_permissions=True)

	def test_affected_employee_from_different_company_is_blocked(self):
		process = self.make_retrenchment_process(num_employees=1)
		other_company_employee = self.make_employee(company="Test PCV Company")
		if other_company_employee.company == process.company:
			self.skipTest("No second distinct Company available on this site to test cross-Company mismatch.")

		process.append(
			"affected_employees",
			{
				"branch": get_reference_branch(),
				"designation": get_reference_designation(),
				"employee": other_company_employee.name,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			process.save(ignore_permissions=True)

	def test_removing_employee_with_served_notice_is_blocked(self):
		process = self.make_retrenchment_process(num_employees=2)
		served_employee = process.affected_employees[0].employee

		notice = frappe.get_doc(
			{
				"doctype": "Section 189 Notice",
				"linked_intervention": process.name,
				"company": process.company,
				"reason_for_dismissals": "Operational requirements",
				"selection_method": "LIFO",
				"recipients": [
					{
						"recipient_type": "Employee",
						"employee": served_employee,
						"date_served": nowdate(),
					}
				],
			}
		)
		notice.insert(ignore_permissions=True)
		self.track("Section 189 Notice", notice.name)

		process.reload()
		process.affected_employees = [
			row for row in process.affected_employees if row.employee != served_employee
		]
		with self.assertRaises(frappe.ValidationError):
			process.save(ignore_permissions=True)

	def test_removing_unserved_employee_is_allowed(self):
		process = self.make_retrenchment_process(num_employees=2)
		removable_employee = process.affected_employees[1].employee

		process.affected_employees = [
			row for row in process.affected_employees if row.employee != removable_employee
		]
		process.save(ignore_permissions=True)

		self.assertEqual(len(process.affected_employees), 1)

	def test_marking_employee_excluded_requires_status_reason(self):
		process = self.make_retrenchment_process(num_employees=1)
		process.affected_employees[0].inclusion_status = "Excluded"

		with self.assertRaises(frappe.ValidationError):
			process.save(ignore_permissions=True)

	def test_marking_employee_excluded_with_reason_succeeds(self):
		process = self.make_retrenchment_process(num_employees=1)
		process.affected_employees[0].inclusion_status = "Excluded"
		process.affected_employees[0].status_reason = "ZZTEST transferred to another role"
		process.save(ignore_permissions=True)

		self.assertEqual(process.affected_employees[0].inclusion_status, "Excluded")

	def test_headcounts_reflect_still_affected_employees(self):
		process = self.make_retrenchment_process(num_employees=2)
		self.assertEqual(process.total_initially_affected, 2)
		self.assertEqual(process.total_still_affected, 2)
		self.assertEqual(process.total_dismissed_12m, 0)

	def test_costing_is_applied_to_affected_employee_rows_on_save(self):
		process = self.make_retrenchment_process(num_employees=1)
		row = process.affected_employees[0]
		row.rate_per_hour = 100
		row.hours_per_day = 9
		row.s189_notice_date = add_months(getdate(nowdate()), -24)
		row.leave_days_projected = 0
		process.save(ignore_permissions=True)

		process.reload()
		saved_row = process.affected_employees[0]
		self.assertGreater(saved_row.estimated_severance_pay, 0)
		self.assertGreater(saved_row.notice_weeks, 0)
		self.assertEqual(process.estimated_total_retrenchment_cost, saved_row.estimated_total_cost)
