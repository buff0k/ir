# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, now_datetime, nowdate

from ir.industrial_relations.doctype.external_dispute_resolution.external_dispute_resolution import (
	get_latest_linked_records,
)
from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_company,
	get_reference_designation,
	synthetic_name,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of External Dispute Resolution's own link-field targets (direct,
# plus the Link targets living inside its own child tables, including the
# applicant_history/Employee Selector ones) is ignored here - this test
# builds its own minimal, synthetic fixtures via make_employee()/
# Contract of Employment instead of letting Frappe recursively
# auto-generate them, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) which assumes a pristine
# site and collides with this site's real Company/Fiscal Year/Employee
# data. "External Dispute Resolution" itself (the self-link inside
# applicant_history's "external_dispute" field) needs no entry - it's the
# doctype under test.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Dispute Resolution Forum",
	"Company",
	"Employee",
	"External Dispute Resolution Outcome",
	"External Dispute Resolution Process",
	"Contract of Employment",
	"Disciplinary Action",
	"Incapacity Proceedings",
	"Appeal Against Outcome",
	"Retrenchment Process",
]

# Real, already-submitted master data this bench's IR module uses for actual
# contracts - deliberately not fabricated (see contract_of_employment's own
# test module for the same reasoning).
REFERENCE_CONTRACT_TYPE = "2.3.MMS Rev.25 - Indefinite"
REFERENCE_CONTRACT_TYPE_2 = "2.2.MMS Rev.25 - Project Based Fixed Term"
REFERENCE_REMUNERATION_SECTION = "Remuneration (Basic Salary No Allowances)"
REFERENCE_WORKING_HOURS_SECTION = "Working Hours (Monday to Friday)"


class IntegrationTestExternalDisputeResolution(IRSyntheticDataTestCase):
	"""Functional tests for External Dispute Resolution's before_submit()
	Outcome guard and the get_latest_linked_records() 'latest record wins'
	resolution logic."""

	def _make_employee(self, **overrides):
		overrides.setdefault("designation", get_reference_designation())
		overrides.setdefault("branch", get_reference_branch())
		overrides.setdefault("za_id_number", "8001015009087")
		return self.make_employee(**overrides)

	def _make_contract(self, employee, contract_type):
		letter_head = frappe.db.get_value("Letter Head", {}, "name", order_by="creation asc")
		doc = frappe.get_doc(
			{
				"doctype": "Contract of Employment",
				"employee": employee.name,
				"contract_type": contract_type,
				"remuneration": REFERENCE_REMUNERATION_SECTION,
				"working_hours": REFERENCE_WORKING_HOURS_SECTION,
				"start_date": nowdate(),
				"rate": 25000,
				"current_address": "123 Test Street, Test Town",
				"letter_head": letter_head,
			}
		)
		doc.insert(ignore_permissions=True)
		self.track("Contract of Employment", doc.name)
		return doc

	def _make_edr(self, **overrides):
		values = {
			"doctype": "External Dispute Resolution",
			"forum": "CCMA",
			"company": get_reference_company(),
			"applicant_external": "ZZTEST Applicant",
			"case_no": synthetic_name("EDR"),
			"respondent_external": "ZZTEST Respondent",
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("External Dispute Resolution", doc.name)
		return doc

	def _set_creation(self, doctype, name, when):
		frappe.db.set_value(doctype, name, "creation", when)

	def test_before_submit_requires_outcome(self):
		edr = self._make_edr()

		with self.assertRaises(frappe.ValidationError):
			edr.submit()

		edr.reload()
		self.assertEqual(edr.docstatus, 0)

		edr.outcome = "Matter Dismissed"
		edr.submit()
		self.assertEqual(edr.docstatus, 1)

	def test_get_latest_linked_records_resolves_latest_contract_by_creation(self):
		employee = self._make_employee()

		older = self._make_contract(employee, REFERENCE_CONTRACT_TYPE)
		newer = self._make_contract(employee, REFERENCE_CONTRACT_TYPE_2)
		self._set_creation("Contract of Employment", older.name, add_days(now_datetime(), -2))
		self._set_creation("Contract of Employment", newer.name, add_days(now_datetime(), -1))

		result = get_latest_linked_records(employee.name)

		self.assertEqual(result["contract"], newer.name)
		self.assertIsNone(result["disc_action"])
		self.assertIsNone(result["incap_proceeding"])
		self.assertIsNone(result["appeal"])
		self.assertIsNone(result["retrenchment"])
		self.assertIsNone(result["external_dispute"])

	def test_get_latest_linked_records_resolves_latest_external_dispute_excluding_self(self):
		employee = self._make_employee()

		edr_a = self._make_edr(applicant_history=[{"applicant": employee.name}])
		edr_b = self._make_edr(applicant_history=[{"applicant": employee.name}])

		# get_latest_linked_records orders by the *child row's* own creation,
		# not the parent EDR's - set that directly.
		child_a = frappe.db.get_value(
			"External Dispute Resolution Applicants",
			{"parent": edr_a.name, "applicant": employee.name},
			"name",
		)
		child_b = frappe.db.get_value(
			"External Dispute Resolution Applicants",
			{"parent": edr_b.name, "applicant": employee.name},
			"name",
		)
		self._set_creation("External Dispute Resolution Applicants", child_a, add_days(now_datetime(), -2))
		self._set_creation("External Dispute Resolution Applicants", child_b, add_days(now_datetime(), -1))

		result_excluding_b = get_latest_linked_records(employee.name, exclude_edr=edr_b.name)
		self.assertEqual(result_excluding_b["external_dispute"], edr_a.name)

		result_overall = get_latest_linked_records(employee.name)
		self.assertEqual(result_overall["external_dispute"], edr_b.name)
