from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import flt

from ir.ir_labour.doctype.business_trip.business_trip import (
	BusinessTrip,
	generate_allowances_for_date_range,
	get_business_trip_mileage_rate,
)
from ir.tests.compat import UnitTestCase


class TestBusinessTrip(UnitTestCase):
	def test_manager_employee_is_mapped_to_manager_user(self):
		doc = frappe.new_doc("Business Trip")
		doc.employee = "EMP-001"
		with patch(
			"frappe.get_cached_value",
			side_effect=[
				frappe._dict(expense_approver=None, reports_to="EMP-MANAGER"),
				"manager@example.com",
			],
		):
			self.assertEqual("manager@example.com", BusinessTrip._get_expense_approver(doc))

	def test_mileage_rate_falls_back_to_date_effective_pack(self):
		with (
			patch("frappe.get_cached_doc", return_value=frappe._dict(mileage_allowance_rate=0)),
			patch(
				"ir.ir_labour.doctype.business_trip.business_trip.get_reimbursive_travel_rate",
				return_value=4.95,
			) as statutory_rate,
		):
			self.assertEqual(4.95, get_business_trip_mileage_rate("2026-04-01"))
		statutory_rate.assert_called_once_with("2026-04-01")

	def test_allowance_generation_requires_region_and_write_permission(self):
		trip = MagicMock()
		trip.docstatus = 0
		trip.from_date = "2026-04-01"
		trip.to_date = "2026-04-03"
		with (
			patch("frappe.get_doc", return_value=trip),
			self.assertRaises(frappe.ValidationError),
		):
			generate_allowances_for_date_range("TRIP-001", None)
		trip.check_permission.assert_called_once_with("write")

	def test_business_trip_totals_use_settings_mileage_rate(self):
		doc = frappe.new_doc("Business Trip")
		doc.from_date = "2026-04-10"
		doc.to_date = "2026-04-11"
		doc.allowances = [
			frappe._dict(daily_rate=522, incidental_rate=169),
			frappe._dict(daily_rate=522, incidental_rate=169),
		]
		doc.journeys = [
			frappe._dict(transport_mode="Car (Private)", distance_km=120, mileage_claim=0),
			frappe._dict(transport_mode="Flight", receipt_amount=1_800),
		]
		doc.accommodations = [frappe._dict(amount=1_250)]
		doc.other_expenses = [frappe._dict(amount=300)]

		with patch("frappe.get_cached_doc", return_value=frappe._dict(mileage_allowance_rate=4.84)):
			BusinessTrip.validate(doc)

		self.assertEqual(1_044, doc.total_allowance)
		self.assertEqual(338, doc.total_incidental)
		self.assertEqual(580.8, flt(doc.total_mileage_claim, 2))
		self.assertEqual(1_800, doc.total_receipt_claims)
		self.assertEqual(1_250, doc.total_accommodation)
		self.assertEqual(300, doc.total_other_expenses)
		self.assertEqual(5_312.8, flt(doc.grand_total, 2))
