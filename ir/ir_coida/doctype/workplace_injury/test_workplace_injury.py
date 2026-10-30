import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_days, today

from ir.ir_coida.doctype.workplace_injury.workplace_injury import WorkplaceInjury
from za_local.tests.compat import UnitTestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


class TestWorkplaceInjury(UnitTestCase):
	def test_workplace_injury_rejects_future_dates_and_calculates_leave_days(self):
		doc = frappe.new_doc("Workplace Injury")
		doc.injury_date = add_days(today(), 1)

		with self.assertRaises(frappe.ValidationError):
			WorkplaceInjury.validate_dates(doc)

		doc.injury_date = "2026-04-01"
		doc.expected_recovery_date = "2026-04-05"
		WorkplaceInjury.calculate_leave_days(doc)
		self.assertEqual(5, doc.leave_days)

	def test_workplace_injury_claim_creation_failure_propagates(self):
		doc = frappe.new_doc("Workplace Injury")
		doc.name = "INJ-TEST"
		doc.employee = "EMP-001"
		doc.company = "Test Company"
		doc.injury_date = "2026-04-01"
		doc.injury_type = "Moderate"
		doc.injury_location = "Warehouse"
		doc.injury_description = "Test injury"
		claim = MagicMock()
		claim.insert.side_effect = frappe.ValidationError("claim insert failed")
		with patch("frappe.new_doc", return_value=claim):
			with self.assertRaises(frappe.ValidationError):
				WorkplaceInjury.create_oid_claim(doc)

	def test_health_doctypes_do_not_grant_employee_role_access(self):
		app_path = Path(frappe.get_app_path("ir"))
		for relative_path in (
			"ir_coida/doctype/workplace_injury/workplace_injury.json",
			"ir_coida/doctype/oid_claim/oid_claim.json",
		):
			payload = json.loads((app_path / relative_path).read_text())
			self.assertNotIn("Employee", {row["role"] for row in payload["permissions"]})
