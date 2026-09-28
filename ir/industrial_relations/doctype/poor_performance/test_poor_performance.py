# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_branch, get_reference_company

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Poor Performance has no validate()/before_submit()/on_submit() overrides
# of its own (its controller is just `class PoorPerformance(Document):
# pass`) - so these tests only exercise required-field validation and the
# standard insert/submit lifecycle. Every one of its own Link-field targets
# (plus its Table children's own Link targets) is ignored here - this test
# builds its own minimal, synthetic fixtures via make_employee()/
# get_reference_*() instead of letting Frappe recursively auto-generate
# them, since that walk pulls in erpnext/hrms's own legacy test-bootstrap
# code which assumes a pristine site and collides with this site's real
# Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Employee",
	"User",
	"Offence Outcome",
]


class IntegrationTestPoorPerformance(IRSyntheticDataTestCase):
	"""Poor Performance has essentially no controller logic beyond field
	defaults - these tests confirm required-field validation and the basic
	insert/submit lifecycle work as expected."""

	def _make_poor_performance(self, employee, complainant, **overrides):
		values = {
			"doctype": "Poor Performance",
			"company": get_reference_company(),
			"employee": employee.name,
			"branch": get_reference_branch(),
			"complainant": complainant.name,
			"request_date": now_datetime(),
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Poor Performance", doc.name)
		return doc

	def test_missing_required_field_raises_mandatory_error(self):
		employee = self.make_employee()

		with self.assertRaises(frappe.MandatoryError):
			frappe.get_doc(
				{
					"doctype": "Poor Performance",
					"company": get_reference_company(),
					"employee": employee.name,
					"branch": get_reference_branch(),
					"request_date": now_datetime(),
					# complainant deliberately omitted - it is reqd=1
				}
			).insert(ignore_permissions=True)

	def test_basic_insert_and_submit_lifecycle(self):
		employee = self.make_employee()
		complainant = self.make_employee()

		doc = self._make_poor_performance(employee, complainant)
		self.assertTrue(doc.name.startswith("PERF-"))
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.employee, employee.name)
		self.assertEqual(doc.complainant, complainant.name)

		doc.submit()
		self.assertEqual(doc.docstatus, 1)
