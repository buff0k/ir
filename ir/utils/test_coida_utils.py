from unittest.mock import MagicMock, patch

import frappe

from ir.utils.coida_utils import (
	get_coida_earnings_by_employee,
	get_company_industry_rate,
	get_oid_claims_for_period,
	get_workplace_injuries_for_period,
)
from za_local.tests.compat import UnitTestCase


class TestCOIDAUtils(UnitTestCase):
	def test_persisted_salary_slip_basis_is_preferred(self):
		salary_slip_meta = MagicMock()
		salary_slip_meta.has_field.side_effect = lambda fieldname: fieldname == "za_coida_basis"
		with (
			patch("frappe.has_permission", return_value=True),
			patch("frappe.get_meta", return_value=salary_slip_meta),
			patch(
				"frappe.db.sql",
				side_effect=[
					[frappe._dict(employee="EMP-001", assessable_total=500000)],
					[frappe._dict(employee="EMP-001", gross_total=550000)],
				],
			) as sql,
		):
			result = get_coida_earnings_by_employee("Test Company", "2026-03-01", "2027-02-28")

		self.assertIn("za_coida_basis", sql.call_args_list[0].args[0])
		self.assertEqual(500000, result["EMP-001"].assessable_total)
		self.assertEqual(550000, result["EMP-001"].gross_total)

	def test_component_applicability_is_used_without_persisted_basis(self):
		salary_slip_meta = MagicMock()
		salary_slip_meta.has_field.return_value = False
		component_meta = MagicMock()
		component_meta.has_field.return_value = True
		detail_meta = MagicMock()
		detail_meta.has_field.return_value = True

		with (
			patch("frappe.has_permission", return_value=True),
			patch("frappe.get_meta", side_effect=[salary_slip_meta, component_meta, detail_meta]),
			patch(
				"frappe.db.sql",
				side_effect=[
					[frappe._dict(employee="EMP-001", assessable_total=400000)],
					[frappe._dict(employee="EMP-001", gross_total=425000)],
				],
			) as sql,
		):
			result = get_coida_earnings_by_employee("Test Company", "2026-03-01", "2027-02-28")

		basis_query = sql.call_args_list[0].args[0]
		self.assertIn("sc.za_coida_applicable", basis_query)
		self.assertIn("sd.parentfield = 'earnings'", basis_query)
		self.assertEqual(400000, result["EMP-001"].assessable_total)

	def test_company_scoped_industry_rate_wins_over_legacy_row(self):
		settings = frappe._dict(
			industry_rates=[
				frappe._dict(company=None, industry_class="Class 1", assessment_rate=1.1),
				frappe._dict(company="Test Company", industry_class="Class 1", assessment_rate=1.25),
			]
		)
		with patch("frappe.get_single", return_value=settings):
			self.assertEqual(1.25, get_company_industry_rate("Test Company", "Class 1"))

	def test_period_helpers_use_correct_fields_and_permission_filtered_lists(self):
		with patch("frappe.get_list", return_value=[]) as get_list:
			get_workplace_injuries_for_period("Test Company", "2026-03-01", "2027-02-28")
			injury_call = get_list.call_args
			self.assertIn("injury_date", injury_call.kwargs["filters"])
			self.assertNotIn("injury_description", injury_call.kwargs["fields"])

		with patch("frappe.get_list", return_value=[]) as get_list:
			get_oid_claims_for_period(
				"Test Company", "2026-03-01", "2027-02-28", status="Under Review"
			)
			claim_call = get_list.call_args
			self.assertEqual("Under Review", claim_call.kwargs["filters"]["claim_status"])
			self.assertNotIn("medical_reports", claim_call.kwargs["fields"])
