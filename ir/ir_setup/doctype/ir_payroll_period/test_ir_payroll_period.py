# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import random_string

# IR Payroll Period has no Link fields of its own, so there are no test
# record dependencies to manage either way.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestIRPayrollPeriod(IntegrationTestCase):
	"""validate_period_days() - period_start/period_end's own min_value/
	max_value aren't enforced on the version-16 branch of frappe yet, so
	this is the real "between 1 and 31" check."""

	def _make(self, period_start, period_end):
		doc = frappe.get_doc({
			"doctype": "IR Payroll Period",
			"payroll_period": f"ZZTEST-{random_string(8)}",
			"period_start": period_start,
			"period_end": period_end,
		})
		doc.insert(ignore_permissions=True)
		return doc

	def tearDown(self):
		frappe.db.delete("IR Payroll Period", {"payroll_period": ["like", "ZZTEST-%"]})
		frappe.db.commit()
		super().tearDown()

	def test_boundary_values_1_and_31_are_accepted(self):
		doc = self._make(1, 31)
		self.assertEqual(doc.period_start, 1)
		self.assertEqual(doc.period_end, 31)

	def test_period_start_zero_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._make(0, 15)

	def test_period_start_above_31_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._make(32, 15)

	def test_period_end_zero_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._make(1, 0)

	def test_period_end_above_31_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._make(1, 45)
