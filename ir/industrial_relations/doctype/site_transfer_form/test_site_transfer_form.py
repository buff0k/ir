# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_company,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Site Transfer Form's own link-field targets is ignored here -
# this test builds its own minimal, synthetic fixtures via make_employee()/
# get_reference_company()/get_reference_branch() instead of letting Frappe
# recursively auto-generate them, since that walk pulls in erpnext/hrms's own
# legacy test-bootstrap code (BootStrapTestData et al) which assumes a
# pristine site and collides with this site's real Company/Fiscal Year/
# Employee data. See test_termination_form.py for the same pattern.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Designation",
	"Branch",
	"Company",
	"Letter Head",
]

DUMMY_ATTACH = "/files/ZZTEST-signed-site-transfer-form.pdf"


def _second_branch(exclude: str | None) -> str:
	"""A second, distinct, real Branch - so a transfer's `new_branch` differs
	from the Employee's own current branch."""
	branch = frappe.db.get_value(
		"Branch", {"name": ["!=", exclude]} if exclude else {}, "name", order_by="creation asc"
	)
	if not branch:
		frappe.throw("Need at least two Branches on this site to test Site Transfer Form.")
	return branch


class IntegrationTestSiteTransferForm(IRSyntheticDataTestCase):
	"""Functional tests for Site Transfer Form's validate()-time field sync
	(requested_by/employee auto-population), the autoname-based duplicate
	guard, and the on_submit Employee.branch/internal_work_history sync."""

	def _make_site_transfer_form(self, employee, new_branch, transfer_date, **overrides):
		values = {
			"doctype": "Site Transfer Form",
			"requested_by": employee.name,
			"employee": employee.name,
			"new_branch": new_branch,
			"transfer_date": transfer_date,
			"reason": "ZZTEST transfer reason",
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Site Transfer Form", doc.name)
		return doc

	def test_validate_autopopulates_employee_and_requester_fields(self):
		company = get_reference_company()
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(company=company, branch=current_branch)

		doc = self._make_site_transfer_form(employee, new_branch, add_days(getdate(nowdate()), 5))

		self.assertEqual(doc.employee_name, employee.employee_name)
		self.assertEqual(doc.requested_by_name, employee.employee_name)
		self.assertEqual(doc.current_branch, current_branch)
		self.assertEqual(doc.company, company)

	def test_before_submit_requires_attach(self):
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(branch=current_branch)
		doc = self._make_site_transfer_form(employee, new_branch, add_days(getdate(nowdate()), 5))

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_on_submit_updates_employee_branch_and_history(self):
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(branch=current_branch)
		transfer_date = add_days(getdate(nowdate()), 5)
		doc = self._make_site_transfer_form(
			employee, new_branch, transfer_date, attach=DUMMY_ATTACH
		)

		doc.submit()

		employee.reload()
		self.assertEqual(employee.branch, new_branch)

		history = employee.get("internal_work_history") or []
		self.assertEqual(len(history), 2)

		closed_row, new_row = history[0], history[1]
		self.assertEqual(closed_row.branch, current_branch)
		self.assertEqual(getdate(closed_row.to_date), transfer_date)
		self.assertEqual(new_row.branch, new_branch)
		self.assertEqual(getdate(new_row.from_date), transfer_date)
		self.assertFalse(new_row.to_date)

	def test_duplicate_employee_branch_and_date_is_blocked(self):
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(branch=current_branch)
		transfer_date = add_days(getdate(nowdate()), 5)

		self._make_site_transfer_form(employee, new_branch, transfer_date)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Site Transfer Form",
					"requested_by": employee.name,
					"employee": employee.name,
					"new_branch": new_branch,
					"transfer_date": transfer_date,
					"reason": "ZZTEST duplicate attempt",
				}
			).insert(ignore_permissions=True)

	def test_second_form_with_different_date_is_allowed(self):
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(branch=current_branch)

		self._make_site_transfer_form(employee, new_branch, add_days(getdate(nowdate()), 5))
		second = self._make_site_transfer_form(
			employee, new_branch, add_days(getdate(nowdate()), 6)
		)
		self.assertTrue(second.name)
