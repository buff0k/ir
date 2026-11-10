# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import re

import frappe
from frappe.utils import add_days, add_years, getdate, nowdate

from ir.ir_setup.doctype.ir_payroll_cost_settings.ir_payroll_cost_settings import get_basic_wage_components
from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_designation,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Contract of Employment's own link-field targets - including
# the new earnings/deductions child tables' own Salary Component link - is
# ignored here. This test builds its own minimal, synthetic fixtures via
# make_employee() and a handful of already-real, already-submitted
# reference master records instead of letting Frappe recursively
# auto-generate them, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) which assumes a pristine
# site and collides with this site's real Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Company",
	"Letter Head",
	"Salary Component",
	"Contract of Employment Earning",
	"Contract of Employment Deduction",
	"Contract of Employment Template",
]

# Names of 2 of the 9 real, permanent, already-submitted Contract of
# Employment Templates this bench's IR module uses for actual contracts -
# deliberately not fabricated, per the same reasoning get_reference_company()/
# get_reference_branch() use for Company/Branch. These were originally
# imported from the now-deleted Contract Type doctype (see contract_name in
# import_legacy_contract_types(), contract_of_employment_template.py) - that
# doctype is gone, but the Templates it produced are permanent, real
# documents in their own right, not derived at test time any more.
REFERENCE_CONTRACT_TYPE = "2.3.MMS Rev.25 - Indefinite"
REFERENCE_CONTRACT_TYPE_2 = "2.2.MMS Rev.25 - Project Based Fixed Term"


def get_reference_letter_head() -> str:
	letter_head = frappe.db.get_value("Letter Head", {}, "name", order_by="creation asc")
	if not letter_head:
		frappe.throw("No Letter Head exists on this site - cannot build synthetic test fixtures.")
	return letter_head


def get_reference_contract_template(contract_type: str) -> str:
	"""The submitted Contract of Employment Template matching this name."""
	template = frappe.db.get_value(
		"Contract of Employment Template", {"contract_name": contract_type, "docstatus": 1}, "name"
	)
	if not template:
		frappe.throw(
			f"No submitted Contract of Employment Template named {contract_type!r} exists - "
			"the Contract Type doctype it was once imported from no longer exists either, so "
			"there's nothing left to self-heal from."
		)
	return template


class IntegrationTestContractOfEmployment(IRSyntheticDataTestCase):
	"""Functional tests for Contract of Employment's wording generation
	(generate_contract, via the Contract of Employment Template engine), its
	required-field guard, and the retirement-date computation applied to the
	linked Employee on submit."""

	def _make_employee(self, **overrides):
		overrides.setdefault("designation", get_reference_designation())
		overrides.setdefault("branch", get_reference_branch())
		overrides.setdefault("za_id_number", "8001015009087")
		return self.make_employee(**overrides)

	def _make_contract(self, employee, contract_type=REFERENCE_CONTRACT_TYPE, **overrides):
		# contract_type itself no longer exists as a field (Contract Type is
		# fully deprecated) - contract_type here is only ever used to
		# resolve the matching contract_template. There's also no separate
		# rate field any more - the rate of pay is just the Earnings row
		# for Basic Salary/Hourly Earnings, same as any allowance. Callers
		# overriding earnings= must include their own basic row if they
		# still want one.
		values = {
			"doctype": "Contract of Employment",
			"employee": employee.name,
			"contract_template": get_reference_contract_template(contract_type),
			"start_date": nowdate(),
			"earnings": [{"salary_component": "Basic Salary", "amount": 25000}],
			"current_address": "123 Test Street, Test Town",
			"letter_head": get_reference_letter_head(),
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Contract of Employment", doc.name)
		return doc

	def test_generate_contract_renders_through_the_template_engine(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		self.assertIsNotNone(contract.generated_contract)
		# pay_basis defaults to Monthly, and this real Contract Type's
		# Remuneration clause carries {{rate}} on its "per month worked"
		# line - both the formatted number and its number-to-words
		# rendering must appear, and no unresolved template syntax must
		# survive into the final HTML.
		self.assertIn("25 000.00", contract.generated_contract)
		self.assertIn("Twenty-Five Thousand", contract.generated_contract)
		self.assertNotIn("{{", contract.generated_contract)
		self.assertNotIn("}}", contract.generated_contract)

	def test_shift_worker_renders_shift_roster_wording_not_fixed_hours(self):
		fixed = self._make_contract(self._make_employee())
		shift_worker = self._make_contract(self._make_employee(), working_hours_type="Shift Worker")

		self.assertNotIn("Shift Roster", fixed.generated_contract)
		self.assertIn("Shift Roster", shift_worker.generated_contract)

	def test_earnings_feed_the_allowance_subclauses(self):
		component = frappe.db.get_value(
			"Salary Component",
			{"type": "Earning", "disabled": 0, "name": ["not in", list(get_basic_wage_components())]},
			"name",
		)
		employee = self._make_employee()
		contract = self._make_contract(
			employee,
			earnings=[
				{"salary_component": "Basic Salary", "amount": 25000},
				{"salary_component": component, "amount": 1500},
			],
		)

		self.assertIn(component, contract.generated_contract)
		self.assertIn("1 500.00", contract.generated_contract)

	def test_basic_earning_row_feeds_the_rate_sentence_and_is_excluded_from_the_table(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		# The "remunerated at a rate of R ..." sentence covers it - it must
		# not also appear as its own numbered allowance sub-clause.
		self.assertIn("25 000.00", contract.generated_contract)
		self.assertNotIn("Basic Salary", contract.generated_contract)

	def test_changing_pay_basis_without_a_matching_earning_row_is_rejected(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		# The existing row is still "Basic Salary" - switching to Hourly
		# with no "Hourly Earnings" row to match must be rejected, not
		# silently left with no rate of pay at all.
		contract.pay_basis = "Hourly"
		with self.assertRaises(frappe.ValidationError):
			contract.save(ignore_permissions=True)

	def test_deduction_row_has_no_amount(self):
		component = frappe.db.get_value("Salary Component", {"type": "Deduction", "disabled": 0}, "name")
		employee = self._make_employee()
		contract = self._make_contract(employee, deductions=[{"salary_component": component}])

		self.assertEqual(len(contract.deductions), 1)
		self.assertFalse(frappe.get_meta("Contract of Employment Deduction").has_field("amount"))

		rows = contract._build_render_context().rows["deductions"]
		self.assertEqual(len(rows), 1)
		self.assertIn(f"<b>{component}</b>", rows[0]["deduction_label"])

	def test_deduction_row_renders_into_the_real_contract_wording(self):
		# Every real imported Template's Deductions section now carries the
		# deductions repeat (deduction_label) in place of its old fixed
		# "UIF/PAYE/Provident Fund/.../Retirement Fund" bullet list
		# (_legacy_deductions() in contract_of_employment_template.py) - so,
		# unlike the direct _build_render_context() check above, this
		# confirms the actual generated_contract itself reflects whatever is
		# really on this contract's own Deductions table.
		component = frappe.db.get_value("Salary Component", {"type": "Deduction", "disabled": 0}, "name")
		employee = self._make_employee()
		contract = self._make_contract(employee, deductions=[{"salary_component": component}])

		self.assertIn(f"<b>{component}</b>", contract.generated_contract)
		self.assertNotIn("UIF (Unemployment", contract.generated_contract)

	def test_multiple_deductions_each_get_their_own_sub_paragraph_number(self):
		# The regression this fix addresses: deductions_table used to cram
		# every Deduction into one unnumbered nested <table>, inside a
		# single numbered sub-paragraph slot - so 2+ deductions were never
		# individually numbered at all. The deductions repeat gives each
		# its own sub-paragraph, same as earnings already does for
		# Allowances (e.g. 4.2.1, 4.2.2).
		components = frappe.get_all(
			"Salary Component", filters={"type": "Deduction", "disabled": 0}, pluck="name", limit=2
		)
		employee = self._make_employee()
		contract = self._make_contract(
			employee, deductions=[{"salary_component": c} for c in components]
		)

		numbers = []
		for component in components:
			match = re.search(rf"<b>([\d.]+)</b></td><td>(?:<b>)?{re.escape(component)}", contract.generated_contract)
			self.assertIsNotNone(match, f"{component} not found as its own numbered row")
			numbers.append(match.group(1))
		self.assertEqual(len(numbers), len(set(numbers)), f"deductions share a sub-paragraph number: {numbers}")

	def test_provident_fund_contribution_defaults_from_contract_defaults(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		expected_rate = frappe.get_cached_doc("Contract Defaults").provident_fund_contribution
		self.assertEqual(contract.provident_fund_contribution, expected_rate)

		context = contract._build_render_context()
		self.assertEqual(context.values["provident_fund_rate"], f"{expected_rate:.2f}%")

	def test_provident_fund_contribution_override_is_not_clobbered_by_the_default(self):
		employee = self._make_employee()
		contract = self._make_contract(employee, provident_fund_contribution=9.5)

		self.assertEqual(contract.provident_fund_contribution, 9.5)

	def test_missing_current_address_is_rejected(self):
		employee = self._make_employee()

		# current_address deliberately omitted here, and the synthetic
		# Employee has none either, so ensure_required_fields() must throw.
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Contract of Employment",
					"employee": employee.name,
					"contract_template": get_reference_contract_template(REFERENCE_CONTRACT_TYPE),
					"start_date": nowdate(),
					"letter_head": get_reference_letter_head(),
				}
			).insert(ignore_permissions=True)

	def test_classification_comes_from_the_template_not_contract_type(self):
		# REFERENCE_CONTRACT_TYPE ("Indefinite") has neither flag;
		# REFERENCE_CONTRACT_TYPE_2 ("Project Based Fixed Term") has
		# has_project=1 - both only via their matching Template now
		# (contract_type itself is deprecated and drives nothing live).
		indefinite = self._make_contract(self._make_employee())
		self.assertEqual(indefinite.has_expiry, 0)
		self.assertEqual(indefinite.has_project, 0)

		project_based = self._make_contract(self._make_employee(), contract_type=REFERENCE_CONTRACT_TYPE_2)
		self.assertEqual(project_based.has_project, 1)

	def test_retirement_date_computed_on_submit(self):
		date_of_birth = getdate("1990-06-15")
		employee = self._make_employee(date_of_birth=date_of_birth)
		contract = self._make_contract(employee)

		# retirement_age/has_retirement are auto-fetched from the Template
		# in validate().
		self.assertEqual(contract.retirement_age, 62)
		self.assertEqual(contract.has_retirement, 1)

		contract.signed_contract = "/files/zztest-signed-contract-of-employment.pdf"
		contract.submit()

		employee.reload()
		expected_retirement_date = add_days(add_years(date_of_birth, 62), -1)
		self.assertEqual(getdate(employee.date_of_retirement), expected_retirement_date)

	def test_submit_without_signed_contract_is_blocked(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		with self.assertRaises(frappe.ValidationError):
			contract.submit()

	def test_generated_contract_is_frozen_after_submit(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)
		contract.signed_contract = "/files/zztest-signed-contract-of-employment.pdf"
		contract.submit()

		frozen_wording = contract.generated_contract

		# A resave of an already-submitted contract (e.g. an allow-on-submit
		# field changing) must never re-render generated_contract - it's
		# what was actually signed.
		contract.reload()
		contract.flags.ignore_validate_update_after_submit = True
		contract.earnings[0].amount = 99999
		contract.save(ignore_permissions=True)

		self.assertEqual(contract.generated_contract, frozen_wording)
