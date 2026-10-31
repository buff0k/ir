# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import now_datetime, nowdate

from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_company,
	get_reference_offence_outcome,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Incapacity Proceedings' only controller logic is before_submit's
# require_outcome_before_submit guard - so these tests exercise
# required-field validation and the insert/submit lifecycle (including that
# guard). Every one of its own Link-field targets (plus its Table children's
# own Link targets) is ignored here - this test builds its own minimal,
# synthetic fixtures via make_employee()/get_reference_*() instead of
# letting Frappe recursively auto-generate them, since that walk pulls in
# erpnext/hrms's own legacy test-bootstrap code which assumes a pristine
# site and collides with this site's real Company/Fiscal Year/Employee
# data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Letter Head",
	"Branch",
	"User",
	"Employee",
	"Type of Incapacity",
	"Offence Outcome",
]


class IntegrationTestIncapacityProceedings(IRSyntheticDataTestCase):
	"""Incapacity Proceedings has essentially no controller logic beyond field
	defaults - these tests confirm required-field validation and the basic
	insert/submit lifecycle work as expected."""

	def _make_proceedings(self, accused, complainant, **overrides):
		values = {
			"doctype": "Incapacity Proceedings",
			"company": get_reference_company(),
			"accused": accused.name,
			"branch": get_reference_branch(),
			"complainant": complainant.name,
			"request_date": now_datetime(),
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Incapacity Proceedings", doc.name)
		return doc

	def test_missing_required_field_raises_mandatory_error(self):
		accused = self.make_employee()
		complainant = self.make_employee()

		with self.assertRaises(frappe.MandatoryError):
			frappe.get_doc(
				{
					"doctype": "Incapacity Proceedings",
					"company": get_reference_company(),
					"accused": accused.name,
					# branch deliberately omitted - it is reqd=1
					"complainant": complainant.name,
					"request_date": now_datetime(),
				}
			).insert(ignore_permissions=True)

	def test_basic_insert_and_submit_lifecycle(self):
		accused = self.make_employee()
		complainant = self.make_employee()
		outcome = get_reference_offence_outcome()
		if not outcome:
			self.skipTest("No Offence Outcome exists on this site.")

		doc = self._make_proceedings(accused, complainant)
		self.assertTrue(doc.name.startswith("INCAP-"))
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.accused, accused.name)
		self.assertEqual(doc.complainant, complainant.name)

		# require_outcome_before_submit blocks submit without these.
		doc.outcome = outcome
		doc.outcome_date = nowdate()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_submit_without_outcome_is_blocked(self):
		accused = self.make_employee()
		complainant = self.make_employee()

		doc = self._make_proceedings(accused, complainant)

		with self.assertRaises(frappe.ValidationError):
			doc.submit()
