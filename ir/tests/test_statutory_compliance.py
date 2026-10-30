"""Statutory rate-pack and compliance-calculation regression tests.

Ported from za_local/tests/test_sa_payroll_compliance_2027.py and
test_sa_payroll_compliance_prior_years.py as part of absorbing za_local
into ir.
"""

import json
from pathlib import Path
from unittest.mock import patch

import frappe

from ir.utils.coida_utils import calculate_annual_coida
from ir.utils.eti_utils import calculate_months_employed
from ir.utils.statutory_rates import (
	calculate_eti_from_pack,
	calculate_tax_from_brackets,
	get_coida_annual_earnings_cap,
	get_rate_pack,
	get_reimbursive_travel_rate,
	get_retirement_annual_cap,
	get_uif_monthly_cap,
)
from ir.utils.tax_utils import calculate_sdl_contribution, calculate_uif_contribution
from ir.utils.termination_utils import calculate_severance_tax
from ir.utils.travel_allowance_utils import (
	calculate_fixed_allowance,
	calculate_reimbursive_allowance,
)
from za_local.tests.compat import UnitTestCase

PRIOR_YEAR_PACKS = {
	"2024-2025": {"date": "2024-03-31", "file": "statutory_rates_2025.json"},
	"2025-2026": {"date": "2025-03-31", "file": "statutory_rates_2026.json"},
}


class TestSAPayrollCompliance2027(UnitTestCase):
	def test_2027_statutory_pack_contains_required_annual_values(self):
		pack = get_rate_pack("2026-03-31")

		self.assertEqual("2026-2027", pack["tax_year"])
		self.assertEqual(17820, pack["paye"]["rebates"]["primary"])
		self.assertEqual(17712, get_uif_monthly_cap("2026-03-31"))
		self.assertEqual(4.95, get_reimbursive_travel_rate("2026-03-31"))
		self.assertEqual(668000, get_coida_annual_earnings_cap("2027-02-28"))
		self.assertEqual(430000, get_retirement_annual_cap("2027-02-28"))

	def test_uif_and_sdl_use_statutory_pack_rates(self):
		self.assertEqual(
			(80, 80),
			tuple(round(v, 2) for v in calculate_uif_contribution(8000, "2026-03-31")),
		)
		self.assertEqual(
			(177.12, 177.12),
			tuple(round(v, 2) for v in calculate_uif_contribution(30000, "2026-03-31")),
		)
		self.assertEqual(300, calculate_sdl_contribution(30000, "2026-03-31"))

	def test_eti_2027_first_and_second_period_amounts(self):
		self.assertEqual(1125, calculate_eti_from_pack(6000, 1, "2026-03-31"))
		self.assertEqual(562.5, calculate_eti_from_pack(6000, 13, "2026-03-31"))
		self.assertEqual(0, calculate_eti_from_pack(7500, 1, "2026-03-31"))

	def test_travel_allowance_helpers_apply_2027_rates(self):
		self.assertEqual(
			{"taxable": 4000, "non_taxable": 1000},
			calculate_fixed_allowance(5000, date_value="2026-03-31"),
		)
		self.assertEqual(
			{
				"total": 1980,
				"taxable": 0,
				"non_taxable": 1980,
				"prescribed_rate": 4.95,
			},
			calculate_reimbursive_allowance(400, date_value="2026-03-31"),
		)
		self.assertEqual(20, calculate_reimbursive_allowance(400, 5.00, "2026-03-31")["taxable"])

	def test_severance_lump_sum_uses_550k_exemption_and_table(self):
		self.assertEqual(0, calculate_severance_tax(550000, "2026-03-31"))
		self.assertEqual(9000, calculate_severance_tax(600000, "2026-03-31"))
		self.assertEqual(39600, calculate_severance_tax(770000, "2026-03-31"))

	def test_coida_annual_calculation_caps_per_employee(self):
		earnings = {
			"EMP-001": frappe._dict(gross_total=900000, assessable_total=900000),
			"EMP-002": frappe._dict(gross_total=300000, assessable_total=300000),
		}

		with (
			patch("ir.utils.coida_utils.get_coida_earnings_by_employee", return_value=earnings),
			patch("ir.utils.coida_utils.get_company_industry_rate", return_value=1.25),
		):
			result = calculate_annual_coida("Test Company", "2026-03-01", "2027-02-28")

		self.assertEqual(1_200_000, result["uncapped_remuneration"])
		self.assertEqual(968_000, result["total_remuneration"])
		self.assertEqual(232_000, result["excluded_remuneration"])
		self.assertEqual(12_100, result["total_coida"])

	def test_salary_component_classification_fields_are_defined(self):
		fixtures = json.loads(
			Path(frappe.get_app_path("ir", "fixtures", "custom_field.json")).read_text()
		)
		fieldnames = {row["fieldname"] for row in fixtures}
		for fieldname in (
			"za_payroll_treatment",
			"za_paye_inclusion_percentage",
			"za_uif_applicable",
			"za_sdl_applicable",
			"za_coida_applicable",
			"za_is_reimbursement",
			"za_variable_pay_treatment",
		):
			self.assertIn(fieldname, fieldnames)

	def test_statutory_rate_pack_json_is_valid(self):
		path = Path(frappe.get_app_path("ir", "ir_setup", "data", "statutory_rates_2027.json"))
		data = json.loads(path.read_text())
		self.assertEqual("2026-2027", data["tax_year"])
		self.assertEqual(7, len(data["paye"]["brackets"]))
		self.assertEqual(4, len(data["eti"]["first_12_months"]))


class TestSAPayrollCompliancePriorYears(UnitTestCase):
	def test_all_tax_years_resolve_without_throwing(self):
		# The original gap: get_rate_pack threw for any date before 2026-03-01.
		for date_value in ("2024-03-31", "2025-03-31", "2026-03-31"):
			pack = get_rate_pack(date_value)
			self.assertIn("paye", pack)

	def test_prior_year_packs_have_expected_metadata_and_paye(self):
		for tax_year, meta in PRIOR_YEAR_PACKS.items():
			pack = get_rate_pack(meta["date"])
			self.assertEqual(tax_year, pack["tax_year"])
			# Brackets were frozen at 2024-2025 levels across both years.
			self.assertEqual(17235, pack["paye"]["rebates"]["primary"])
			self.assertEqual(9444, pack["paye"]["rebates"]["secondary"])
			self.assertEqual(3145, pack["paye"]["rebates"]["tertiary"])
			self.assertEqual(95750, pack["paye"]["thresholds"]["under_65"])
			self.assertEqual(7, len(pack["paye"]["brackets"]))
			self.assertEqual(17712, get_uif_monthly_cap(meta["date"]))
			self.assertEqual(364, pack["medical_tax_credit"]["main_member"])
			self.assertEqual(246, pack["medical_tax_credit"]["additional_dependant"])

	def test_prior_year_paye_brackets_compute_correctly(self):
		for meta in PRIOR_YEAR_PACKS.values():
			brackets = get_rate_pack(meta["date"])["paye"]["brackets"]
			self.assertEqual(18000, calculate_tax_from_brackets(100000, brackets))
			self.assertEqual(59032, calculate_tax_from_brackets(300000, brackets))
			self.assertEqual(189677, calculate_tax_from_brackets(700000, brackets))

	def test_2024_2025_eti_uses_legacy_band_structure(self):
		# SARS table effective from 1 March 2022 through 31 March 2025.
		d = "2024-03-31"
		self.assertEqual(1125, calculate_eti_from_pack(1500, 1, d))
		self.assertEqual(1500, calculate_eti_from_pack(3000, 1, d))
		self.assertEqual(750, calculate_eti_from_pack(5500, 1, d))
		self.assertEqual(0, calculate_eti_from_pack(6500, 1, d))     # above ceiling
		self.assertEqual(750, calculate_eti_from_pack(3000, 13, d))

	def test_2025_2026_eti_switches_on_1_april_2025(self):
		self.assertEqual(750, calculate_eti_from_pack(5500, 1, "2025-03-31"))
		self.assertEqual(1500, calculate_eti_from_pack(5500, 1, "2025-04-01"))
		self.assertEqual(0, calculate_eti_from_pack(7000, 1, "2025-03-31"))
		self.assertEqual(375, calculate_eti_from_pack(7000, 1, "2025-04-01"))

	def test_less_than_160_hours_uses_grossed_up_remuneration(self):
		self.assertEqual(0, calculate_eti_from_pack(4000, 1, "2025-04-30", hours_per_month=80))
		self.assertEqual(750, calculate_eti_from_pack(1500, 1, "2025-04-30", hours_per_month=80))
		self.assertEqual(0, calculate_eti_from_pack(1500, 1, "2025-04-30", hours_per_month=0))

	def test_prior_year_annually_gazetted_values(self):
		self.assertEqual(4.84, get_reimbursive_travel_rate("2024-03-31"))
		self.assertEqual(4.76, get_reimbursive_travel_rate("2025-04-01"))
		self.assertEqual(597328, get_coida_annual_earnings_cap("2024-03-31"))
		self.assertEqual(633168, get_coida_annual_earnings_cap("2025-04-01"))
		self.assertEqual(548, get_rate_pack("2024-03-31")["subsistence"]["rsa_meals_and_incidentals_per_day"])
		self.assertEqual(570, get_rate_pack("2025-04-01")["subsistence"]["rsa_meals_and_incidentals_per_day"])

	def test_prior_year_pack_json_is_valid(self):
		for tax_year, meta in PRIOR_YEAR_PACKS.items():
			path = Path(frappe.get_app_path("ir", "ir_setup", "data", meta["file"]))
			data = json.loads(path.read_text())
			self.assertEqual(tax_year, data["tax_year"])
			self.assertEqual(7, len(data["paye"]["brackets"]))
			self.assertEqual(4, len(data["eti"]["first_12_months"]))

	def test_future_rate_pack_probe_is_non_throwing(self):
		from ir.utils.statutory_rates import find_rate_pack

		self.assertIsNone(find_rate_pack("2027-03-01"))

	def test_future_statutory_calculation_still_fails_loudly(self):
		with self.assertRaises(Exception):
			get_rate_pack("2027-03-01")


class TestETIMonthsEmployed(UnitTestCase):
	"""Lock in the calendar-month ETI count (joining month is month 1)."""

	def test_joining_month_counts_as_month_one(self):
		self.assertEqual(1, calculate_months_employed("2024-01-15", "2024-01-31"))

	def test_subsequent_calendar_month_increments(self):
		self.assertEqual(2, calculate_months_employed("2024-01-15", "2024-02-10"))

	def test_month_end_joiner_is_not_undercounted(self):
		# Previously a 31st-of-month joiner was undercounted the following month
		# because the day-of-month comparison failed.
		self.assertEqual(2, calculate_months_employed("2024-01-31", "2024-02-01"))

	def test_twelfth_and_thirteenth_month_boundary(self):
		self.assertEqual(12, calculate_months_employed("2024-01-01", "2024-12-01"))
		self.assertEqual(13, calculate_months_employed("2023-01-01", "2024-01-01"))

	def test_current_date_before_joining_returns_zero(self):
		self.assertEqual(0, calculate_months_employed("2024-02-01", "2024-01-01"))
