# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, add_years, getdate, nowdate

from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_designation,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Contract of Employment's own link-field targets is ignored
# here (Employee/Company/Contract Type/Letter Head/Contract Section) - this
# test builds its own minimal, synthetic fixtures via make_employee() and a
# handful of already-real, already-submitted reference master records
# (Contract Type/Contract Section/Letter Head) instead of letting Frappe
# recursively auto-generate them, since that walk pulls in erpnext/hrms's own
# legacy test-bootstrap code (BootStrapTestData et al) which assumes a
# pristine site and collides with this site's real Company/Fiscal
# Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Company",
	"Contract Type",
	"Letter Head",
	"Contract Section",
]

# Real, already-submitted master data that this bench's IR module uses for
# actual contracts - deliberately not fabricated, per the same reasoning
# get_reference_company()/get_reference_branch() use for Company/Branch.
REFERENCE_CONTRACT_TYPE = "2.3.MMS Rev.25 - Indefinite"
REFERENCE_CONTRACT_TYPE_2 = "2.2.MMS Rev.25 - Project Based Fixed Term"
REFERENCE_REMUNERATION_SECTION = "Remuneration (Basic Salary No Allowances)"
REFERENCE_WORKING_HOURS_SECTION = "Working Hours (Monday to Friday)"


def get_reference_letter_head() -> str:
	letter_head = frappe.db.get_value("Letter Head", {}, "name", order_by="creation asc")
	if not letter_head:
		frappe.throw("No Letter Head exists on this site - cannot build synthetic test fixtures.")
	return letter_head


class IntegrationTestContractOfEmployment(IRSyntheticDataTestCase):
	"""Functional tests for Contract of Employment's clause-generation
	(update_contract_clauses/generate_contract), its required-field
	guard, and the retirement-date computation applied to the linked
	Employee on submit."""

	def _make_employee(self, **overrides):
		overrides.setdefault("designation", get_reference_designation())
		overrides.setdefault("branch", get_reference_branch())
		overrides.setdefault("za_id_number", "8001015009087")
		return self.make_employee(**overrides)

	def _make_contract(self, employee, contract_type=REFERENCE_CONTRACT_TYPE, **overrides):
		values = {
			"doctype": "Contract of Employment",
			"employee": employee.name,
			"contract_type": contract_type,
			"remuneration": REFERENCE_REMUNERATION_SECTION,
			"working_hours": REFERENCE_WORKING_HOURS_SECTION,
			"start_date": nowdate(),
			"rate": 25000,
			"current_address": "123 Test Street, Test Town",
			"letter_head": get_reference_letter_head(),
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Contract of Employment", doc.name)
		return doc

	def test_update_contract_clauses_generates_rows_from_contract_type(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		self.assertGreater(len(contract.contract_clauses), 0)

		# One header row per section in the Contract Type's contract_terms -
		# "Position" is one of its real, unconditional (non-placeholder)
		# sections, so its header must appear verbatim.
		header_rows = [row.clause_content for row in contract.contract_clauses]
		self.assertTrue(any("<b>Position</b>" in content for content in header_rows))

		# Every contract_clauses row must have been stamped with a
		# section_number (the Contract Type's own sec_no for that section).
		self.assertTrue(all(row.section_number for row in contract.contract_clauses))

	def test_generate_contract_replaces_placeholders_with_real_values(self):
		employee = self._make_employee()
		contract = self._make_contract(employee)

		self.assertIsNotNone(contract.generated_contract)
		# {rate} is actually referenced by this real Contract Type's
		# Remuneration clause text, so both the formatted number and its
		# number-to-words rendering must appear, and the raw token must not.
		self.assertIn("25 000.00", contract.generated_contract)
		self.assertIn("Twenty-Five Thousand", contract.generated_contract)
		self.assertNotIn("{rate}", contract.generated_contract)
		self.assertNotIn("{restraint_period}", contract.generated_contract)

	def test_missing_current_address_is_rejected(self):
		employee = self._make_employee()

		# current_address deliberately omitted here, and the synthetic
		# Employee has none either, so ensure_required_fields() must throw.
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Contract of Employment",
					"employee": employee.name,
					"contract_type": REFERENCE_CONTRACT_TYPE,
					"remuneration": REFERENCE_REMUNERATION_SECTION,
					"working_hours": REFERENCE_WORKING_HOURS_SECTION,
					"start_date": nowdate(),
					"rate": 25000,
					"letter_head": get_reference_letter_head(),
				}
			).insert(ignore_permissions=True)

	def test_retirement_date_computed_on_submit(self):
		date_of_birth = getdate("1990-06-15")
		employee = self._make_employee(date_of_birth=date_of_birth)
		contract = self._make_contract(employee)

		# retirement_age is auto-fetched from the Contract Type in validate().
		self.assertEqual(contract.retirement_age, 62)

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
