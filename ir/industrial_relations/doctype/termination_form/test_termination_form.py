# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_company

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Termination Form's own link-field targets is ignored here -
# this test builds its own minimal, synthetic fixtures via make_employee()/
# get_reference_company() instead of letting Frappe recursively auto-generate
# them, since that walk pulls in erpnext/hrms's own legacy test-bootstrap
# code (BootStrapTestData et al) which assumes a pristine site and collides
# with this site's real Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Letter Head",
	"Company",
	"Retrenchment Process",
	"Employee",
	"Designation",
	"Branch",
	"Reason for Termination",
	"Termination Documentation",
]

EXISTING_REASON = "Dismissal for Misconduct"


class IntegrationTestTerminationForm(IRSyntheticDataTestCase):
	"""Functional tests for Termination Form's Employee sync logic:
	relieving_date/status computation, the reports_to chain clearing, and
	the duplicate-employee-and-date guard."""

	def _make_termination_form(self, employee, termination_date, **overrides):
		company = overrides.pop("company", None) or get_reference_company()
		values = {
			"doctype": "Termination Form",
			"company": company,
			"requested_by": employee.name,
			"requested_for": employee.name,
			"reason": EXISTING_REASON,
			"termination_date": termination_date,
			"id_number": "0000000000000",
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Termination Form", doc.name)
		return doc

	def test_past_termination_date_marks_employee_left(self):
		employee = self.make_employee()
		past_date = add_days(getdate(nowdate()), -10)

		self._make_termination_form(employee, past_date)

		employee.reload()
		self.assertEqual(employee.status, "Left")
		self.assertEqual(getdate(employee.relieving_date), past_date)
		self.assertEqual(employee.reason_for_leaving, EXISTING_REASON)

	def test_future_termination_date_keeps_employee_active(self):
		employee = self.make_employee()
		future_date = add_days(getdate(nowdate()), 30)

		self._make_termination_form(employee, future_date)

		employee.reload()
		self.assertEqual(employee.status, "Active")
		self.assertEqual(getdate(employee.relieving_date), future_date)

	def test_relieving_date_is_later_of_termination_date_and_notice_ends(self):
		employee = self.make_employee()
		termination_date = add_days(getdate(nowdate()), 10)
		notice_ends = add_days(getdate(nowdate()), 40)

		self._make_termination_form(employee, termination_date, notice_ends=notice_ends)

		employee.reload()
		self.assertEqual(getdate(employee.relieving_date), notice_ends)

	def test_duplicate_employee_and_date_is_blocked(self):
		employee = self.make_employee()
		termination_date = add_days(getdate(nowdate()), -5)

		self._make_termination_form(employee, termination_date)

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "Termination Form",
					"company": get_reference_company(),
					"requested_by": employee.name,
					"requested_for": employee.name,
					"reason": EXISTING_REASON,
					"termination_date": termination_date,
					"id_number": "0000000000000",
				}
			).insert(ignore_permissions=True)

	def test_second_form_with_different_date_is_allowed(self):
		employee = self.make_employee()
		self._make_termination_form(employee, add_days(getdate(nowdate()), -5))
		second = self._make_termination_form(employee, add_days(getdate(nowdate()), -1))
		self.assertTrue(second.name)

	def test_terminating_a_manager_clears_direct_reports(self):
		manager = self.make_employee()
		report = self.make_employee(reports_to=manager.name)

		self._make_termination_form(manager, add_days(getdate(nowdate()), -1))

		report.reload()
		self.assertFalse(report.reports_to)

	def test_submit_reruns_sync_and_allows_submission(self):
		employee = self.make_employee()
		past_date = add_days(getdate(nowdate()), -3)
		doc = self._make_termination_form(employee, past_date)

		doc.submit()

		employee.reload()
		self.assertEqual(employee.status, "Left")
		self.assertEqual(doc.docstatus, 1)
