from unittest.mock import patch

import frappe

from ir.ir_payroll.doctype.emp201_submission.emp201_submission import (
	EMP201Submission,
	calculate_eti_utilisation,
)
from za_local.tests.compat import UnitTestCase


class TestEMP201Submission(UnitTestCase):
	def test_emp201_submission_key_is_deterministic_for_company_period(self):
		first = frappe.new_doc("EMP201 Submission")
		first.update({"company": "Test Company", "fiscal_year": "2026-2027", "month": "March"})
		second = frappe.new_doc("EMP201 Submission")
		second.update({"company": "Test Company", "fiscal_year": "2026-2027", "month": "March"})

		EMP201Submission.set_submission_key(first)
		EMP201Submission.set_submission_key(second)

		self.assertEqual(first.submission_key, second.submission_key)
		self.assertEqual(64, len(first.submission_key))

	def test_emp201_month_is_resolved_from_fiscal_year_dates_not_name(self):
		doc = frappe.new_doc("EMP201 Submission")
		doc.month = "January"
		doc.fiscal_year = "SA Tax Year FY26"
		fiscal_year = frappe._dict(year_start_date="2025-03-01", year_end_date="2026-02-28")

		with patch("frappe.get_doc", return_value=fiscal_year):
			result = EMP201Submission.set_submission_period_dates(doc)

		self.assertEqual("2026-01-01", str(result["submission_period_start_date"]))
		self.assertEqual("2026-01-31", str(result["submission_period_end_date"]))

	def test_emp201_fetch_data_aggregates_sars_mapped_components(self):
		doc = frappe.new_doc("EMP201 Submission")
		doc.company = "Test Company"
		doc.submission_period_start_date = "2026-04-01"
		doc.submission_period_end_date = "2026-04-30"

		salary_slip = frappe._dict(
			{
				"za_monthly_eti": 200,
				"deductions": [
					frappe._dict(salary_component="PAYE", amount=1_500),
					frappe._dict(salary_component="UIF Employee", amount=177.12),
				],
				"company_contribution": [
					frappe._dict(salary_component="SDL Contribution", amount=250),
				],
				"earnings": [],
			}
		)

		def bucket(component_name):
			return {
				"PAYE": ("paye", frappe._dict()),
				"UIF Employee": ("uif", frappe._dict()),
				"SDL Contribution": ("sdl", frappe._dict()),
			}.get(component_name, (None, frappe._dict()))

		with (
			patch("frappe.get_all", return_value=[frappe._dict(name="SAL-SLIP-0001")]),
			patch("frappe.get_doc", return_value=salary_slip),
			patch("frappe.db.get_value", return_value=0),
			patch(
				"ir.ir_payroll.doctype.emp201_submission.emp201_submission._get_emp201_bucket",
				side_effect=bucket,
			),
		):
			result = EMP201Submission.fetch_emp201_data(doc)

		self.assertEqual(1_500, result["gross_paye_before_eti"])
		self.assertEqual(200, result["eti_generated_current_month"])
		self.assertEqual(200, result["eti_utilized_current_month"])
		self.assertEqual(1_300, result["net_paye_payable"])
		self.assertEqual(177.12, result["uif_payable"])
		self.assertEqual(250, result["sdl_payable"])


class TestEmployerEtiUtilisation(UnitTestCase):
	def test_eti_utilisation_is_capped_at_employer_paye_liability(self):
		result = calculate_eti_utilisation(10_000, 12_000, 2_000, "2026-07-01")

		self.assertEqual(result.eti_utilized_current_month, 10_000)
		self.assertEqual(result.net_paye_payable, 0)
		self.assertEqual(result.eti_to_be_carried_forward, 4_000)

	def test_september_opening_balance_is_always_zero(self):
		result = calculate_eti_utilisation(5_000, 2_000, 8_000, "2026-09-01")

		self.assertEqual(result.eti_carried_forward_from_previous, 0)
		self.assertEqual(result.total_eti_available, 2_000)
		self.assertEqual(result.eti_reconciliation_refund, 0)

	def test_august_unused_eti_is_ring_fenced_for_refund(self):
		result = calculate_eti_utilisation(5_000, 4_000, 3_000, "2026-08-01")

		self.assertEqual(result.eti_utilized_current_month, 5_000)
		self.assertEqual(result.eti_to_be_carried_forward, 0)
		self.assertEqual(result.eti_reconciliation_refund, 2_000)

	def test_emp201_eti_refund_closes_each_six_month_reconciliation_cycle(self):
		august = calculate_eti_utilisation(1_000, 300, 900, "2026-08-01")
		self.assertEqual(1_000, august.eti_utilized_current_month)
		self.assertEqual(200, august.eti_reconciliation_refund)
		self.assertEqual(0, august.eti_to_be_carried_forward)

		september = calculate_eti_utilisation(1_000, 300, 900, "2026-09-01")
		self.assertEqual(0, september.eti_carried_forward_from_previous)
		self.assertEqual(300, september.eti_utilized_current_month)
