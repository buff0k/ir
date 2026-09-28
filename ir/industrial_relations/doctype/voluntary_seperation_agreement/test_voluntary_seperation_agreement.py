# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_designation,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Voluntary Seperation Agreement's own link-field targets is
# ignored here - this test builds its own minimal, synthetic fixtures via
# make_employee()/a synthetic Poor Performance record instead of letting
# Frappe recursively auto-generate them, since that walk pulls in
# erpnext/hrms's own legacy test-bootstrap code (BootStrapTestData et al)
# which assumes a pristine site and collides with this site's real
# Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Company",
	"Letter Head",
	"Disciplinary Action",
	"Designation",
	"Offence Outcome",
	"Incapacity Proceedings",
	"Poor Performance",
]

# Real, already-existing "termination" Offence Outcome this bench's IR
# module uses for actual VSPs - deliberately not fabricated.
REFERENCE_VSP_OFFENCE_OUTCOME = "VSP"


class IntegrationTestVoluntarySeperationAgreement(IRSyntheticDataTestCase):
	"""Functional tests for Voluntary Seperation Agreement's docstatus-aware
	linked-document syncing (clear on save, set on submit, db_set +
	create_manual_version when the linked document is already submitted)
	and its before_submit() Employee status/relieving-date update."""

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

	def _make_vsp(self, employee, poor_performance, **overrides):
		values = {
			"doctype": "Voluntary Seperation Agreement",
			"employee": employee.name,
			"linked_poor_performance": poor_performance.name,
			"names": employee.employee_name,
			"coy": employee.name,
			"position": get_reference_designation(),
			"outcome_date": nowdate(),
			"auth_manager": employee.name,
			"effective_date": add_days(nowdate(), 30),
			"release_date": add_days(nowdate(), 30),
			"notice_ends": add_days(nowdate(), 30),
			"payment_date": add_days(nowdate(), 35),
			"completed_years": 5,
			"vsp_type": REFERENCE_VSP_OFFENCE_OUTCOME,
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Voluntary Seperation Agreement", doc.name)
		return doc

	def test_before_save_clears_draft_linked_document_outcome(self):
		employee = self._make_employee()
		poor_performance = self._make_poor_performance(
			employee, outcome=REFERENCE_VSP_OFFENCE_OUTCOME, outcome_date=nowdate()
		)
		poor_performance.reload()
		self.assertEqual(poor_performance.outcome, REFERENCE_VSP_OFFENCE_OUTCOME)

		# clear_outcome_in_linked_documents() runs from before_save() on the
		# VSP's very first insert, since the linked Poor Performance is
		# still a draft (docstatus 0).
		self._make_vsp(employee, poor_performance)

		poor_performance.reload()
		self.assertFalse(poor_performance.outcome)
		self.assertFalse(poor_performance.outcome_date)

	def test_submit_sets_employee_left_and_draft_linked_document_outcome(self):
		employee = self._make_employee()
		poor_performance = self._make_poor_performance(employee)
		notice_ends = add_days(nowdate(), 45)

		vsp = self._make_vsp(employee, poor_performance, notice_ends=notice_ends)
		vsp.submit()

		employee.reload()
		self.assertEqual(employee.status, "Left")
		self.assertEqual(getdate(employee.relieving_date), getdate(notice_ends))

		poor_performance.reload()
		self.assertEqual(poor_performance.outcome, REFERENCE_VSP_OFFENCE_OUTCOME)
		self.assertEqual(getdate(poor_performance.outcome_date), getdate(vsp.outcome_date))

	def test_submit_without_notice_ends_is_blocked(self):
		employee = self._make_employee()
		poor_performance = self._make_poor_performance(employee)
		vsp = self._make_vsp(employee, poor_performance)

		# notice_ends is also a mandatory DocType field, so exercise
		# before_submit()'s own explicit guard specifically (rather than the
		# generic mandatory-field check) by bypassing that check.
		vsp.notice_ends = None
		vsp.flags.ignore_mandatory = True

		with self.assertRaises(frappe.ValidationError):
			vsp.submit()

	def test_submit_updates_already_submitted_linked_document_via_db_set_and_version(self):
		employee = self._make_employee()
		poor_performance = self._make_poor_performance(employee)
		poor_performance.submit()
		self.assertEqual(poor_performance.docstatus, 1)

		vsp = self._make_vsp(employee, poor_performance)

		before_versions = frappe.db.count(
			"Version", {"ref_doctype": "Poor Performance", "docname": poor_performance.name}
		)

		vsp.submit()

		poor_performance.reload()
		self.assertEqual(poor_performance.outcome, REFERENCE_VSP_OFFENCE_OUTCOME)
		self.assertEqual(getdate(poor_performance.outcome_date), getdate(vsp.outcome_date))

		after_versions = frappe.db.count(
			"Version", {"ref_doctype": "Poor Performance", "docname": poor_performance.name}
		)
		self.assertGreater(after_versions, before_versions)

		# create_manual_version() inserts real Version docs on the submitted
		# linked document's docstatus==1 branch - clean every one of them up.
		for version_name in frappe.get_all(
			"Version",
			filters={"ref_doctype": "Poor Performance", "docname": poor_performance.name},
			pluck="name",
		):
			self.track("Version", version_name)
