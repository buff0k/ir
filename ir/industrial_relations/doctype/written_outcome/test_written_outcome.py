# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import now_datetime, nowdate

from ir.industrial_relations.doctype.written_outcome.written_outcome import (
	fetch_intervention_data,
	get_outcome_body,
)
from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_designation,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Written Outcome's own link-field targets (direct, plus the
# Link targets living inside its own child tables) is ignored here - this
# test builds its own minimal, synthetic fixtures via make_employee()/a
# synthetic Poor Performance record instead of letting Frappe recursively
# auto-generate them, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) which assumes a pristine
# site and collides with this site's real Company/Fiscal Year/Employee
# data. "linked_intervention" is a Dynamic Link (options points at the
# ir_intervention fieldname, not a fixed doctype), so Frappe's dependency
# walker can't resolve a concrete target for it and it needs no entry here.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Letter Head",
	"DocType",
	"Employee",
	"Designation",
	"Branch",
	"NTA Enquiry",
	"Type of Incapacity",
	"Offence Outcome",
	"Disciplinary Offence",
	"Disciplinary Action",
	"Incapacity Proceedings",
	"Poor Performance",
	"Appeal Against Outcome",
]


class IntegrationTestWrittenOutcome(IRSyntheticDataTestCase):
	"""Functional tests for Written Outcome's stable revision-numbered
	autoname(), the continuous Annexure-letter numbering across the
	complainant/accused evidence tables, and the NTA-charges-vs-final-charges
	splicing performed by get_outcome_body()."""

	def _make_employee(self, **overrides):
		overrides.setdefault("designation", get_reference_designation())
		overrides.setdefault("branch", get_reference_branch())
		return self.make_employee(**overrides)

	def _make_poor_performance(self, employee, **overrides):
		values = {
			"doctype": "Poor Performance",
			"employee": employee.name,
			"complainant": employee.name,
			"branch": get_reference_branch(),
			"request_date": now_datetime(),
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Poor Performance", doc.name)
		return doc

	def _make_written_outcome(self, employee, poor_performance, **overrides):
		values = {
			"doctype": "Written Outcome",
			"ir_intervention": "Poor Performance",
			"linked_intervention": poor_performance.name,
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"employee_designation": get_reference_designation(),
			"employee_branch": get_reference_branch(),
			"chairperson": employee.name,
			"chairperson_name": employee.employee_name,
			"complainant": employee.name,
			"complainant_name": employee.employee_name,
			"enquiry_date": nowdate(),
			"outcome_date": nowdate(),
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Written Outcome", doc.name)
		return doc

	def _make_appeal_against_outcome(self, employee, poor_performance, **overrides):
		values = {
			"doctype": "Appeal Against Outcome",
			"employee": employee.name,
			"names": employee.employee_name,
			"position": get_reference_designation(),
			"branch": get_reference_branch(),
			"company": employee.company,
			# _validate_intervention() requires a real linked record of a
			# supported type - Poor Performance is one, and reusing
			# _make_poor_performance() keeps this fixture minimal.
			"ir_intervention": "Poor Performance",
			"linked_intervention": poor_performance.name,
			"appeal_decision": "Pending",
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True, ignore_mandatory=True)
		self.track("Appeal Against Outcome", doc.name)
		return doc

	def test_fetch_intervention_data_maps_appeal_against_outcome_employee_fields(self):
		# Regression test: Appeal Against Outcome has no appellant/
		# appellant_name fields - the real fields are employee/names. A
		# stale field_maps entry referencing appellant/appellant_name broke
		# this with a raw MySQL "Unknown column" error, since
		# fetch_intervention_data() builds its column list straight from
		# field_maps and hands it to frappe.db.get_value(). Also covers
		# Position/Site (employee_designation/employee_branch), which the
		# original field_maps entry dropped entirely - unlike Disciplinary
		# Action's own mapping, which does carry those across.
		employee = self._make_employee()
		poor_performance = self._make_poor_performance(employee)
		appeal = self._make_appeal_against_outcome(employee, poor_performance)

		result = fetch_intervention_data(
			intervention=appeal.name, intervention_type="Appeal Against Outcome"
		)

		self.assertEqual(result["employee"], employee.name)
		self.assertEqual(result["employee_name"], employee.employee_name)
		self.assertEqual(result["employee_designation"], appeal.position)
		self.assertEqual(result["employee_branch"], appeal.branch)
		self.assertEqual(result["company"], employee.company)

	def test_autoname_first_record_and_revision_numbering(self):
		employee = self._make_employee()
		poor_performance = self._make_poor_performance(employee)

		first = self._make_written_outcome(employee, poor_performance)
		self.assertEqual(first.name, f"OUT-{poor_performance.name}")

		second = self._make_written_outcome(employee, poor_performance)
		self.assertEqual(second.name, f"OUT-{poor_performance.name}-1")

		third = self._make_written_outcome(employee, poor_performance)
		self.assertEqual(third.name, f"OUT-{poor_performance.name}-2")

	def test_assign_annexure_letters_spans_both_evidence_tables(self):
		# Built and validated purely in-memory (never inserted) - the
		# annexure-numbering logic only touches doc.get()/doc.append(), so
		# no DB row (and therefore no cleanup) is needed for this test.
		doc = frappe.get_doc({"doctype": "Written Outcome"})
		doc.append("complainant_evidence", {"evidence_description": "Complainant doc 1"})
		doc.append("complainant_evidence", {"evidence_description": "Complainant doc 2"})
		doc.append("accused_evidence", {"evidence_description": "Accused doc 1"})

		doc._assign_annexure_letters()

		self.assertEqual(doc.complainant_evidence[0].evidence_annexure, "Annexure A")
		self.assertEqual(doc.complainant_evidence[1].evidence_annexure, "Annexure B")
		# Continuous single sequence across both tables, complainant rows first.
		self.assertEqual(doc.accused_evidence[0].evidence_annexure, "Annexure C")

		# Recomputed on every call - removing a row shifts the remaining letters.
		doc.complainant_evidence = doc.complainant_evidence[:1]
		doc._assign_annexure_letters()
		self.assertEqual(doc.complainant_evidence[0].evidence_annexure, "Annexure A")
		self.assertEqual(doc.accused_evidence[0].evidence_annexure, "Annexure B")

	def test_get_outcome_body_splices_nta_and_final_charges_by_intervention_type(self):
		# Also purely in-memory - get_outcome_body() only reads doc.get(),
		# so it needs no saved record.
		doc = frappe.get_doc(
			{
				"doctype": "Written Outcome",
				"ir_intervention": "Disciplinary Action",
				"summary_introduction": "The matter was referred to a disciplinary enquiry.",
				"summary_finding": "The chairperson found the employee guilty.",
			}
		)
		doc.append("nta_charges", {"indiv_charge": "Insubordination as per the NTA"})
		doc.append("final_charges", {"code_item": "", "charge": "Gross Insubordination (final)"})

		html, footnotes = get_outcome_body(doc)

		self.assertEqual(footnotes, [])
		# NTA charges are spliced in right after Introduction, final charges
		# right after Finding - both sections keep the continuous [n]
		# numbering going, they don't reset it.
		introduction_pos = html.index("Introduction")
		nta_heading_pos = html.index("Charges as per NTA")
		nta_charge_pos = html.index("Insubordination as per the NTA")
		finding_pos = html.index("Finding")
		final_heading_pos = html.index("Final Charges")
		final_charge_pos = html.index("Gross Insubordination (final)")

		self.assertLess(introduction_pos, nta_heading_pos)
		self.assertLess(nta_heading_pos, nta_charge_pos)
		self.assertLess(nta_charge_pos, finding_pos)
		self.assertLess(finding_pos, final_heading_pos)
		self.assertLess(final_heading_pos, final_charge_pos)

		# Continuous numbering: [1] Introduction, [2] the (single) NTA charge
		# point, [3] Finding, [4] the (single) final charge point.
		self.assertIn("[1]", html)
		self.assertIn("[2]", html)
		self.assertIn("[3]", html)
		self.assertIn("[4]", html)
		self.assertLess(html.index("[1]"), html.index("[2]"))
		self.assertLess(html.index("[2]"), html.index("[3]"))
		self.assertLess(html.index("[3]"), html.index("[4]"))
