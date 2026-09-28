# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import getdate, now_datetime, nowdate

from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_branch, get_reference_company

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Dismissal Form's own Link-field targets (plus its Table
# children's own Link targets) is ignored here - this test builds its own
# minimal, synthetic fixtures via make_employee()/get_reference_*() instead
# of letting Frappe recursively auto-generate them, since that walk pulls in
# erpnext/hrms's own legacy test-bootstrap code (BootStrapTestData et al)
# which assumes a pristine site and collides with this site's real
# Company/Fiscal Year/Employee data. "DocType" is ignored too, since
# ir_intervention is itself a Link to DocType.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Offence Outcome",
	"Employee",
	"Company",
	"Letter Head",
	"Employee Rights",
	"DocType",
	"Disciplinary Action",
	"Incapacity Proceedings",
	"Poor Performance",
]


def _reference_disciplinary_offence() -> str | None:
	return frappe.db.get_value("Disciplinary Offence", {}, "name", order_by="creation asc")


def _reference_dismissal_type() -> str | None:
	return frappe.db.get_value("Offence Outcome", {"istermination": 1}, "name", order_by="creation asc")


def _reference_employee_rights() -> str | None:
	return frappe.db.get_value("Employee Rights", {}, "name", order_by="creation asc")


class IntegrationTestDismissalForm(IRSyntheticDataTestCase):
	"""Functional tests for Dismissal Form's:
	- _validate_intervention (unsupported/missing/non-existent linked
	  intervention throws)
	- before_submit's Employee status -> Left / relieving_date sync
	- on_cancel's reinstate-employee logic
	- the source-outcome clear (before_save)/set (on_submit)/clear
	  (on_cancel) cycle, for the Disciplinary Action intervention.
	"""

	def _make_disciplinary_action(self, accused, complainant):
		code_item = _reference_disciplinary_offence()
		if not code_item:
			self.skipTest("No Disciplinary Offence exists on this site.")

		doc = frappe.get_doc(
			{
				"doctype": "Disciplinary Action",
				"company": get_reference_company(),
				"accused": accused.name,
				"branch": get_reference_branch(),
				"complainant": complainant.name,
				"request_date": now_datetime(),
				"offences": [
					{
						"code_item": code_item,
						"offence_datetime": now_datetime(),
						"incident_details": "ZZTEST synthetic incident details.",
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		self.track("Disciplinary Action", doc.name)
		doc.submit()
		return doc

	def _dismissal_values(self, **overrides):
		dismissal_type = _reference_dismissal_type()
		applied_rights = _reference_employee_rights()
		if not dismissal_type:
			self.skipTest("No terminating Offence Outcome exists on this site.")
		if not applied_rights:
			self.skipTest("No Employee Rights record exists on this site.")

		values = {
			"doctype": "Dismissal Form",
			"names": "ZZTEST",
			"position": "ZZTEST",
			"dismissal_type": dismissal_type,
			"outcome_date": nowdate(),
			"applied_rights": applied_rights,
			"signed_dismissal": "/files/zztest-signed-dismissal.pdf",
		}
		values.update(overrides)
		return values

	def _make_dismissal_form(self, source, employee, **overrides):
		values = self._dismissal_values(
			ir_intervention="Disciplinary Action",
			linked_intervention=source.name,
			employee=employee.name,
			names=employee.employee_name or "ZZTEST",
		)
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Dismissal Form", doc.name)
		return doc

	def test_validate_rejects_unsupported_intervention(self):
		employee = self.make_employee()
		# "User" is a real DocType (so Link validation on ir_intervention
		# passes) but is not in SUPPORTED_INTERVENTIONS - this exercises
		# _validate_intervention()'s own check, not generic link validation.
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				self._dismissal_values(
					ir_intervention="User",
					linked_intervention="Administrator",
					employee=employee.name,
				)
			).insert(ignore_permissions=True)

	def test_validate_rejects_missing_linked_intervention(self):
		employee = self.make_employee()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				self._dismissal_values(
					ir_intervention="Disciplinary Action",
					linked_intervention=None,
					employee=employee.name,
				)
			).insert(ignore_permissions=True)

	def test_validate_rejects_non_existent_linked_intervention(self):
		employee = self.make_employee()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				self._dismissal_values(
					ir_intervention="Disciplinary Action",
					linked_intervention="DISC-ZZTEST-DOES-NOT-EXIST",
					employee=employee.name,
				)
			).insert(ignore_permissions=True)

	def test_submit_marks_employee_left_and_sets_relieving_date(self):
		employee = self.make_employee()
		complainant = self.make_employee()
		source = self._make_disciplinary_action(employee, complainant)
		dismissal = self._make_dismissal_form(source, employee, outcome_date=nowdate())

		dismissal.submit()

		employee.reload()
		self.assertEqual(employee.status, "Left")
		self.assertEqual(getdate(employee.relieving_date), getdate(nowdate()))

	def test_cancel_reinstates_employee(self):
		employee = self.make_employee()
		complainant = self.make_employee()
		source = self._make_disciplinary_action(employee, complainant)
		dismissal = self._make_dismissal_form(source, employee)
		dismissal.submit()

		dismissal.cancel()

		employee.reload()
		self.assertEqual(employee.status, "Active")
		self.assertFalse(employee.relieving_date)

	def test_source_outcome_is_cleared_on_insert_set_on_submit_and_cleared_again_on_cancel(self):
		employee = self.make_employee()
		complainant = self.make_employee()
		source = self._make_disciplinary_action(employee, complainant)

		# Simulate a pre-existing outcome on the source, as if some other
		# final-outcome document had already set it - so before_save's
		# clearing behaviour is actually observable.
		dismissal_type = _reference_dismissal_type()
		frappe.db.set_value(
			"Disciplinary Action",
			source.name,
			{"outcome": dismissal_type, "outcome_date": nowdate()},
		)

		# before_save (run as part of insert()) clears the source's outcome
		# fields unconditionally, before this Dismissal Form is even saved.
		dismissal = self._make_dismissal_form(source, employee)

		source.reload()
		self.assertFalse(source.outcome)
		self.assertFalse(source.outcome_date)

		dismissal.submit()

		source.reload()
		self.assertEqual(source.outcome, dismissal.dismissal_type)
		self.assertEqual(getdate(source.outcome_date), getdate(dismissal.outcome_date))

		dismissal.cancel()

		source.reload()
		self.assertFalse(source.outcome)
		self.assertFalse(source.outcome_date)
