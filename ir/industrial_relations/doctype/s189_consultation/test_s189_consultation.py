# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe

from ir.tests.test_helpers import IRSyntheticDataTestCase

# On IntegrationTestCase, the doctype test records and all link-field test
# record dependencies are recursively loaded. Use these module variables to
# add/remove to/from that list.
#
# Every one of S189 Consultation's own Link targets is ignored here - its
# direct fields (self-referencing amended_from, ir_intervention -> DocType,
# linked_intervention -> Retrenchment Process, company) and every Link field
# on its child table (S189 Consultation Attendee: employee/trade_union) -
# this test builds its own minimal, synthetic fixtures via make_employee()/
# make_retrenchment_process() instead of letting Frappe recursively
# auto-generate them, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) which assumes a pristine site
# and collides with this site's real Company/Fiscal Year/Employee data.
# Ignoring "Retrenchment Process"/"Trade Union" here also stops the walk from
# recursing further into THEIR own link targets.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"S189 Consultation",
	"DocType",
	"Retrenchment Process",
	"Company",
	"Employee",
	"Trade Union",
]


class IntegrationTestS189Consultation(IRSyntheticDataTestCase):
	"""Functional tests for S189 Consultation's before_submit guard (at least
	one Attendee) and the populate_attendees/populate_union_attendees
	filtering logic (only currently-Affected, non-dismissed employees, and
	unions with members among them)."""

	def _make_consultation(self, process, **overrides):
		values = {
			"doctype": "S189 Consultation",
			"linked_intervention": process.name,
			"company": process.company,
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("S189 Consultation", doc.name)
		return doc

	def _make_trade_union(self, company):
		union = frappe.get_doc(
			{
				"doctype": "Trade Union",
				"name": frappe.generate_hash(length=8) + " ZZTEST Union",
				"full_union_name_not_acronym": "ZZTEST Amalgamated Test Workers Union",
				"co_list": [{"recognized_company": company}],
				"of_list": [{"of_name": "ZZTEST Official", "of_pos": "Secretary"}],
			}
		)
		union.insert(ignore_permissions=True)
		self.track("Trade Union", union.name)
		return union

	def test_submit_without_attendees_is_blocked(self):
		process = self.make_retrenchment_process(num_employees=1)
		consultation = self._make_consultation(process)

		with self.assertRaises(frappe.ValidationError):
			consultation.submit()

	def test_submit_with_attendee_succeeds(self):
		process = self.make_retrenchment_process(num_employees=1)
		employee_name = process.affected_employees[0].employee
		consultation = self._make_consultation(
			process,
			attendees=[{"attendee_type": "Employee", "employee": employee_name, "represented_by": "Self"}],
		)

		consultation.submit()

		self.assertEqual(consultation.docstatus, 1)

	def test_populate_attendees_includes_only_affected_employees(self):
		from ir.industrial_relations.doctype.s189_consultation.s189_consultation import populate_attendees

		process = self.make_retrenchment_process(num_employees=2)
		still_affected = process.affected_employees[0].employee
		excluded = process.affected_employees[1].employee

		process.affected_employees[1].inclusion_status = "Excluded"
		process.affected_employees[1].status_reason = "ZZTEST no longer affected"
		process.save(ignore_permissions=True)

		attendees = populate_attendees(process.name)
		attendee_employees = {row["employee"] for row in attendees}

		self.assertIn(still_affected, attendee_employees)
		self.assertNotIn(excluded, attendee_employees)
		for row in attendees:
			self.assertEqual(row["attendee_type"], "Employee")
			self.assertEqual(row["represented_by"], "Self")

	def test_populate_attendees_excludes_employees_with_outcome(self):
		from ir.industrial_relations.doctype.s189_consultation.s189_consultation import populate_attendees

		process = self.make_retrenchment_process(num_employees=2)
		dismissed_employee = process.affected_employees[0].employee

		# Simulate a recorded dismissal outcome directly on the row (this is
		# what Dismissal Form submission would set via db_set on the real
		# path) - populate_attendees must treat any row with an outcome as no
		# longer up for consultation, regardless of inclusion_status.
		frappe.db.set_value(
			"Retrenchment Affected Employee",
			process.affected_employees[0].name,
			{"outcome": "ZZTEST-OUTCOME", "outcome_date": frappe.utils.nowdate()},
		)

		attendees = populate_attendees(process.name)
		attendee_employees = {row["employee"] for row in attendees}

		self.assertNotIn(dismissed_employee, attendee_employees)

	def test_populate_union_attendees_returns_membership(self):
		from ir.industrial_relations.doctype.s189_consultation.s189_consultation import populate_union_attendees

		process = self.make_retrenchment_process(num_employees=1)
		employee = frappe.get_doc("Employee", process.affected_employees[0].employee)
		union = self._make_trade_union(process.company)
		employee.db_set("custom_trade_union", union.name)

		rows = populate_union_attendees(process.name)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["attendee_type"], "Trade Union")
		self.assertEqual(rows[0]["trade_union"], union.name)
		self.assertEqual(rows[0]["contact_name"], "ZZTEST Official")

	def test_populate_union_attendees_empty_when_no_members(self):
		from ir.industrial_relations.doctype.s189_consultation.s189_consultation import populate_union_attendees

		process = self.make_retrenchment_process(num_employees=1)

		rows = populate_union_attendees(process.name)

		self.assertEqual(rows, [])
