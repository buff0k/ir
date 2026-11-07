# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Designation",
	"Branch",
	"Company",
	"Letter Head",
]


def _second_branch(exclude: str | None) -> str:
	branch = frappe.db.get_value(
		"Branch", {"name": ["!=", exclude]} if exclude else {}, "name", order_by="creation asc"
	)
	if not branch:
		frappe.throw("Need at least two Branches on this site to test Site Transfer Form.")
	return branch


class IntegrationTestSiteTransferForm(IRSyntheticDataTestCase):
	"""Site Transfer Form is deprecated - superseded by Status Change Form's
	own current_branch/new_branch fields. The only behaviour left to test is
	that creating a new one is blocked; existing records stay readable."""

	def test_new_site_transfer_form_is_blocked(self):
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(branch=current_branch)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": "Site Transfer Form",
				"requested_by": employee.name,
				"employee": employee.name,
				"new_branch": new_branch,
				"transfer_date": add_days(getdate(nowdate()), 5),
				"reason": "ZZTEST transfer reason",
			}).insert(ignore_permissions=True)
