# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.utils import nowdate

from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_company

# On IntegrationTestCase, the doctype test records and all link-field test
# record dependencies are recursively loaded. Use these module variables to
# add/remove to/from that list.
#
# Every one of Section 189 Notice's own Link targets is ignored here - its
# direct fields (self-referencing amended_from, ir_intervention -> DocType,
# linked_intervention -> Retrenchment Process, company, issued_by -> User) and
# every Link field on its two child tables (Section 189 Notice Designation:
# designation; Section 189 Notice Recipient: employee/trade_union) - this test
# builds its own minimal, synthetic fixtures via make_employee()/
# make_retrenchment_process() instead of letting Frappe recursively
# auto-generate them, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) which assumes a pristine site
# and collides with this site's real Company/Fiscal Year/Employee data.
# Ignoring "Retrenchment Process"/"User"/"Trade Union"/"Designation" here also
# stops the walk from recursing further into THEIR own link targets.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Section 189 Notice",
	"DocType",
	"Retrenchment Process",
	"Company",
	"User",
	"Designation",
	"Employee",
	"Trade Union",
]


class IntegrationTestSection189Notice(IRSyntheticDataTestCase):
	"""Functional tests for Section 189 Notice's before_submit guards: at
	least one Recipient, and every Trade Union with members among the
	Retrenchment Process's affected employees must be a covered Recipient."""

	def _make_notice(self, process, **overrides):
		values = {
			"doctype": "Section 189 Notice",
			"linked_intervention": process.name,
			"company": process.company,
			"reason_for_dismissals": "ZZTEST operational requirements",
			"selection_method": "ZZTEST LIFO by date of joining",
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Section 189 Notice", doc.name)
		return doc

	def _make_trade_union(self, company):
		union = frappe.get_doc(
			{
				"doctype": "Trade Union",
				"name": frappe.generate_hash(length=8) + " ZZTEST Union",
				"full_union_name_not_acronym": "ZZTEST Amalgamated Test Workers Union",
				"co_list": [{"recognized_company": company}],
				"of_list": [{"of_name": "ZZTEST Official", "of_pos": "Secretary", "of_mail": "zztest@example.com"}],
			}
		)
		union.insert(ignore_permissions=True)
		self.track("Trade Union", union.name)
		return union

	def test_submit_without_recipients_is_blocked(self):
		process = self.make_retrenchment_process(num_employees=1)
		notice = self._make_notice(process)

		with self.assertRaises(frappe.ValidationError):
			notice.submit()

	def test_submit_with_recipient_and_no_union_members_succeeds(self):
		process = self.make_retrenchment_process(num_employees=1)
		employee_name = process.affected_employees[0].employee
		notice = self._make_notice(
			process,
			recipients=[{"recipient_type": "Employee", "employee": employee_name}],
		)

		notice.submit()

		self.assertEqual(notice.docstatus, 1)

	def test_submit_missing_union_recipient_is_blocked(self):
		process = self.make_retrenchment_process(num_employees=1)
		employee = frappe.get_doc("Employee", process.affected_employees[0].employee)
		union = self._make_trade_union(process.company)
		employee.db_set("custom_trade_union", union.name)

		notice = self._make_notice(
			process,
			recipients=[{"recipient_type": "Employee", "employee": employee.name}],
		)

		with self.assertRaises(frappe.ValidationError):
			notice.submit()

	def test_submit_with_covered_union_recipient_succeeds(self):
		process = self.make_retrenchment_process(num_employees=1)
		employee = frappe.get_doc("Employee", process.affected_employees[0].employee)
		union = self._make_trade_union(process.company)
		employee.db_set("custom_trade_union", union.name)

		notice = self._make_notice(
			process,
			recipients=[
				{"recipient_type": "Employee", "employee": employee.name},
				{"recipient_type": "Trade Union", "trade_union": union.name, "contact_name": "ZZTEST Official"},
			],
		)

		notice.submit()

		self.assertEqual(notice.docstatus, 1)

	def test_populate_recipients_skips_excluded_and_dismissed_rows(self):
		from ir.industrial_relations.doctype.section_189_notice.section_189_notice import populate_recipients

		process = self.make_retrenchment_process(num_employees=2)
		included_employee = process.affected_employees[0].employee
		excluded_employee = process.affected_employees[1].employee

		process.affected_employees[1].inclusion_status = "Excluded"
		process.affected_employees[1].status_reason = "ZZTEST no longer affected"
		process.save(ignore_permissions=True)

		recipients = populate_recipients(process.name)
		recipient_employees = {row["employee"] for row in recipients}

		self.assertIn(included_employee, recipient_employees)
		self.assertNotIn(excluded_employee, recipient_employees)

	def test_populate_union_recipients_returns_membership(self):
		from ir.industrial_relations.doctype.section_189_notice.section_189_notice import populate_union_recipients

		process = self.make_retrenchment_process(num_employees=1)
		employee = frappe.get_doc("Employee", process.affected_employees[0].employee)
		union = self._make_trade_union(process.company)
		employee.db_set("custom_trade_union", union.name)

		rows = populate_union_recipients(process.name)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["recipient_type"], "Trade Union")
		self.assertEqual(rows[0]["trade_union"], union.name)
		self.assertEqual(rows[0]["contact_name"], "ZZTEST Official")

	def test_fetch_from_process_pulls_statutory_fields(self):
		from ir.industrial_relations.doctype.section_189_notice.section_189_notice import fetch_from_process

		process = self.make_retrenchment_process(num_employees=1)
		process.alternatives_considered = "ZZTEST considered short time"
		process.save(ignore_permissions=True)

		data = fetch_from_process(process.name)

		self.assertEqual(data["reason_for_dismissals"], process.reason_for_dismissals)
		self.assertEqual(data["selection_method"], process.selection_method)
		self.assertEqual(data["alternatives_considered"], "ZZTEST considered short time")
		self.assertEqual(data["total_initially_affected"], process.total_initially_affected)
