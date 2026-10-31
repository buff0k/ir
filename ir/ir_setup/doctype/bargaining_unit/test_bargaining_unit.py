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
# Company/Designation are real, existing site data (see test_helpers.py's own
# reasoning for why these are never auto-generated on this live site).
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Designation", "Trade Union"]


class IntegrationTestBargainingUnit(IRSyntheticDataTestCase):
	"""autoname()'s Company-BU Name-Inception Date composition and its
	duplicate-prevention check."""

	def _make_bargaining_unit(self, **overrides):
		company = overrides.pop("company", None) or get_reference_company()
		designation = overrides.pop("designation", None) or get_reference_designation()

		values = {
			"doctype": "Bargaining Unit",
			"company": company,
			"bu_name": overrides.pop("bu_name", "ZZTEST Shaft Unit"),
			"create_date": overrides.pop("create_date", nowdate()),
			"applicable_designations": [{"designation": designation}],
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Bargaining Unit", doc.name)
		return doc

	def test_autoname_composes_company_bu_name_and_inception_date(self):
		company = get_reference_company()
		doc = self._make_bargaining_unit(company=company, bu_name="ZZTEST Autoname Unit", create_date=nowdate())

		self.assertEqual(doc.name, f"{company}-ZZTEST Autoname Unit-{getdate(nowdate())}")

	def test_duplicate_company_bu_name_and_date_is_rejected(self):
		company = get_reference_company()
		self._make_bargaining_unit(company=company, bu_name="ZZTEST Duplicate Unit", create_date=nowdate())

		with self.assertRaises(frappe.ValidationError):
			self._make_bargaining_unit(company=company, bu_name="ZZTEST Duplicate Unit", create_date=nowdate())

	def test_same_name_and_company_on_a_different_date_is_allowed(self):
		company = get_reference_company()
		first = self._make_bargaining_unit(
			company=company, bu_name="ZZTEST Revised Unit", create_date=nowdate()
		)
		second = self._make_bargaining_unit(
			company=company,
			bu_name="ZZTEST Revised Unit",
			create_date=add_days(nowdate(), -1),
		)

		self.assertNotEqual(first.name, second.name)
