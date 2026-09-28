# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_company,
	get_reference_designation,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Status Change Form's own link-field targets is ignored here -
# this test builds its own minimal, synthetic fixtures via make_employee()/
# get_reference_company()/get_reference_designation() instead of letting
# Frappe recursively auto-generate them, since that walk pulls in erpnext/
# hrms's own legacy test-bootstrap code (BootStrapTestData et al) which
# assumes a pristine site and collides with this site's real Company/Fiscal
# Year/Employee data. See test_termination_form.py for the same pattern.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Designation",
	"Company",
	"Letter Head",
]

DUMMY_ATTACH = "/files/ZZTEST-signed-status-change-form.pdf"

# Every "current_*"/"new_*" Currency/Select field is reqd=1 on this doctype -
# zero-value defaults for all of them, so tests only override what they
# actually care about.
_ZERO_MONEY_FIELDS = {
	"current_conditions": "Indefinite",
	"new_conditions": "Indefinite",
	"current_rate": 0,
	"new_rate": 0,
	"current_travel": 0,
	"new_travel": 0,
	"current_housing": 0,
	"new_housing": 0,
	"current_safety": 0,
	"new_safety": 0,
	"current_shift": 0,
	"new_shift": 0,
	"current_phone": 0,
	"new_phone": 0,
	"current_opencast": 0,
	"new_opencast": 0,
}


def _second_designation(exclude: str | None) -> str:
	"""A second, distinct, real Designation - so a status change's
	`new_designation` differs from the Employee's own current designation."""
	designation = frappe.db.get_value(
		"Designation",
		{"name": ["!=", exclude]} if exclude else {},
		"name",
		order_by="creation asc",
	)
	if not designation:
		frappe.throw("Need at least two Designations on this site to test Status Change Form.")
	return designation


class IntegrationTestStatusChangeForm(IRSyntheticDataTestCase):
	"""Functional tests for Status Change Form's validate()-time field sync
	(requested_by/current_designation auto-population), the autoname-based
	duplicate guard, and the on_submit Employee.designation/
	internal_work_history sync - which only fires when the designation
	actually changes."""

	def _make_status_change_form(self, employee, new_designation, effective_date, **overrides):
		values = {
			"doctype": "Status Change Form",
			"requested_by": employee.name,
			"employee": employee.name,
			"new_designation": new_designation,
			"effective_date": effective_date,
			"reason": "ZZTEST status change reason",
		}
		values.update(_ZERO_MONEY_FIELDS)
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Status Change Form", doc.name)
		return doc

	def test_validate_autopopulates_employee_and_requester_fields(self):
		company = get_reference_company()
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(company=company, designation=current_designation)

		doc = self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 5)
		)

		self.assertEqual(doc.employee_name, employee.employee_name)
		self.assertEqual(doc.requested_by_name, employee.employee_name)
		self.assertEqual(doc.current_designation, current_designation)
		self.assertEqual(doc.company, company)

	def test_before_submit_requires_attach(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(designation=current_designation)
		doc = self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 5)
		)

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_on_submit_updates_employee_designation_and_history_when_changed(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		branch = frappe.db.get_value("Branch", {}, "name", order_by="creation asc")
		employee = self.make_employee(designation=current_designation, branch=branch)
		effective_date = add_days(getdate(nowdate()), 5)

		doc = self._make_status_change_form(
			employee, new_designation, effective_date, attach=DUMMY_ATTACH
		)
		doc.submit()

		employee.reload()
		self.assertEqual(employee.designation, new_designation)

		history = employee.get("internal_work_history") or []
		self.assertEqual(len(history), 2)

		closed_row, new_row = history[0], history[1]
		self.assertEqual(closed_row.designation, current_designation)
		self.assertEqual(closed_row.branch, branch)
		self.assertEqual(getdate(closed_row.to_date), effective_date)
		self.assertEqual(new_row.designation, new_designation)
		self.assertEqual(new_row.branch, branch)
		self.assertEqual(getdate(new_row.from_date), effective_date)
		self.assertFalse(new_row.to_date)

	def test_on_submit_is_a_no_op_when_designation_unchanged(self):
		current_designation = get_reference_designation()
		employee = self.make_employee(designation=current_designation)
		effective_date = add_days(getdate(nowdate()), 5)

		# new_designation intentionally the same as the Employee's own
		# current designation - on_submit's own comment says branch/history
		# are only touched when the designation actually changes.
		doc = self._make_status_change_form(
			employee, current_designation, effective_date, attach=DUMMY_ATTACH
		)
		doc.submit()

		employee.reload()
		self.assertEqual(employee.designation, current_designation)
		self.assertEqual(employee.get("internal_work_history") or [], [])

	def test_duplicate_employee_designation_and_date_is_blocked(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(designation=current_designation)
		effective_date = add_days(getdate(nowdate()), 5)

		self._make_status_change_form(employee, new_designation, effective_date)

		with self.assertRaises(frappe.ValidationError):
			values = {
				"doctype": "Status Change Form",
				"requested_by": employee.name,
				"employee": employee.name,
				"new_designation": new_designation,
				"effective_date": effective_date,
				"reason": "ZZTEST duplicate attempt",
			}
			values.update(_ZERO_MONEY_FIELDS)
			frappe.get_doc(values).insert(ignore_permissions=True)

	def test_second_form_with_different_date_is_allowed(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(designation=current_designation)

		self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 5)
		)
		second = self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 6)
		)
		self.assertTrue(second.name)
