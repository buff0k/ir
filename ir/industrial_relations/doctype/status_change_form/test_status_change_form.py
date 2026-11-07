# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.industrial_relations.doctype.status_change_form.status_change_detail_backfill import (
	build_status_change_detail_rows,
	classify_rate_component,
)
from ir.tests.test_helpers import (
	IRSyntheticDataTestCase,
	get_reference_branch,
	get_reference_company,
	get_reference_designation,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Status Change Form's own link-field targets is ignored here -
# this test builds its own minimal, synthetic fixtures via make_employee()/
# get_reference_company()/get_reference_designation() instead of letting
# Frappe recursively auto-generate them, since that walk pulls in erpnext/
# hrms's own legacy test-bootstrap code (BootStrapTestData et al) which
# assumes a pristine site and collides with this site's real Company/Fiscal
# Year/Employee data. See test_termination_form.py for the same pattern.
#
# "Salary Component" is here because of the new Status Change Detail child
# table's salary_component Link field - Salary Component's own "accounts"
# child table links to Company/Account, which walks into the same
# Company/Fiscal Year bootstrap collision.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Designation",
	"Company",
	"Letter Head",
	"Salary Component",
]

DUMMY_ATTACH = "/files/ZZTEST-signed-status-change-form.pdf"


def _second_designation(exclude: str | None) -> str:
	"""A second, distinct, real Designation - so a status change's
	`new_designation` differs from the Employee's own current designation."""
	designation = frappe.db.get_value(
		"Designation",
		{"name": ["!=", exclude]} if exclude else {},
		"name",
		order_by="creation asc",
	)
	if not designation:
		frappe.throw("Need at least two Designations on this site to test Status Change Form.")
	return designation


def _second_branch(exclude: str | None) -> str:
	"""A second, distinct, real Branch - so a status change's `new_branch`
	differs from the Employee's own current branch."""
	branch = frappe.db.get_value(
		"Branch", {"name": ["!=", exclude]} if exclude else {}, "name", order_by="creation asc"
	)
	if not branch:
		frappe.throw("Need at least two Branches on this site to test Status Change Form.")
	return branch


class IntegrationTestStatusChangeForm(IRSyntheticDataTestCase):
	"""Functional tests for Status Change Form's validate()-time field sync
	(requested_by/current_designation/current_branch auto-population), the
	autoname-based duplicate guard, and the on_submit Employee.designation/
	Employee.branch/internal_work_history sync - which fires independently
	for whichever of designation or branch actually changed."""

	# ---- pure-function tests: no DB needed, for the Status Change Detail
	# backfill patch's row-building logic -------------------------------

	def test_classify_rate_component_cutoff(self):
		self.assertEqual(classify_rate_component(1000), "Hourly Earnings")
		self.assertEqual(classify_rate_component(1000.0), "Hourly Earnings")
		self.assertEqual(classify_rate_component(1000.01), "Basic Salary")
		self.assertEqual(classify_rate_component(0), "Hourly Earnings")

	def test_build_detail_rows_is_empty_when_nothing_changed(self):
		source = {
			"current_designation": "Boilermaker", "new_designation": "Boilermaker",
			"current_branch": None, "new_branch": None,
			"current_conditions": "", "new_conditions": "",
			"current_rate": 500, "new_rate": 500,
			"current_travel": 0, "new_travel": 0,
			"current_housing": 0, "new_housing": 0,
			"current_safety": 0, "new_safety": 0,
			"current_shift": 0, "new_shift": 0,
			"current_phone": 0, "new_phone": 0,
			"current_opencast": 0, "new_opencast": 0,
		}
		self.assertEqual(build_status_change_detail_rows(source), [])

	def test_build_detail_rows_designation_change(self):
		source = {"current_designation": "Boilermaker", "new_designation": "Fitter"}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [{
			"change_type": "Designation", "old_value": "Boilermaker", "new_value": "Fitter",
		}])

	def test_build_detail_rows_branch_null_to_null_is_skipped(self):
		"""A record predating the Branch field ever existing on this form -
		both sides None, not a real change."""
		source = {"current_branch": None, "new_branch": None}
		self.assertEqual(build_status_change_detail_rows(source), [])

	def test_build_detail_rows_branch_change(self):
		source = {"current_branch": "Bankfontein", "new_branch": "Isambane"}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [{
			"change_type": "Branch", "old_value": "Bankfontein", "new_value": "Isambane",
		}])

	def test_build_detail_rows_conditions_blank_to_blank_is_skipped(self):
		"""A migrated-from-Site-Transfer-Form record, where Conditions was
		left at its default blank on both sides - not a real change."""
		source = {"current_conditions": "", "new_conditions": ""}
		self.assertEqual(build_status_change_detail_rows(source), [])

	def test_build_detail_rows_conditions_change(self):
		source = {"current_conditions": "Fixed Term", "new_conditions": "Indefinite"}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [{
			"change_type": "Conditions of Employment",
			"old_condition": "Fixed Term", "new_condition": "Indefinite",
		}])

	def test_build_detail_rows_simple_allowance_change(self):
		source = {"current_travel": 100, "new_travel": 250}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [{
			"change_type": "Salary Component", "salary_component": "Transport Allowance",
			"old_amount": 100.0, "new_amount": 250.0,
		}])

	def test_build_detail_rows_simple_allowance_unchanged_is_skipped(self):
		source = {"current_shift": 50, "new_shift": 50}
		self.assertEqual(build_status_change_detail_rows(source), [])

	def test_build_detail_rows_rate_change_same_side_of_cutoff(self):
		source = {"current_rate": 500, "new_rate": 700}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [{
			"change_type": "Salary Component", "salary_component": "Hourly Earnings",
			"old_amount": 500.0, "new_amount": 700.0,
		}])

	def test_build_detail_rows_rate_change_crosses_cutoff_hourly_to_basic(self):
		source = {"current_rate": 500, "new_rate": 5000}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [
			{"change_type": "Salary Component", "salary_component": "Hourly Earnings",
			 "old_amount": 500.0, "new_amount": 0},
			{"change_type": "Salary Component", "salary_component": "Basic Salary",
			 "old_amount": 0, "new_amount": 5000.0},
		])

	def test_build_detail_rows_rate_change_crosses_cutoff_basic_to_hourly(self):
		source = {"current_rate": 5000, "new_rate": 500}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [
			{"change_type": "Salary Component", "salary_component": "Basic Salary",
			 "old_amount": 5000.0, "new_amount": 0},
			{"change_type": "Salary Component", "salary_component": "Hourly Earnings",
			 "old_amount": 0, "new_amount": 500.0},
		])

	def test_build_detail_rows_rate_unchanged_is_skipped(self):
		source = {"current_rate": 5000, "new_rate": 5000}
		self.assertEqual(build_status_change_detail_rows(source), [])

	def test_build_detail_rows_rate_crossover_from_zero_omits_vacuous_old_row(self):
		"""current_rate=0 classifies as Hourly Earnings by the cutoff rule,
		but a literal 0 never actually held an hourly rate - only the real
		Basic Salary row should come out, not a spurious 0->0 Hourly row."""
		source = {"current_rate": 0, "new_rate": 5000}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [
			{"change_type": "Salary Component", "salary_component": "Basic Salary",
			 "old_amount": 0, "new_amount": 5000.0},
		])

	def test_build_detail_rows_rate_crossover_to_zero_omits_vacuous_new_row(self):
		source = {"current_rate": 5000, "new_rate": 0}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [
			{"change_type": "Salary Component", "salary_component": "Basic Salary",
			 "old_amount": 5000.0, "new_amount": 0},
		])

	def test_build_detail_rows_combined_scenario(self):
		source = {
			"current_designation": "Boilermaker", "new_designation": "Fitter",
			"current_branch": "Bankfontein", "new_branch": "Bankfontein",
			"current_conditions": "Fixed Term", "new_conditions": "Fixed Term",
			"current_rate": 500, "new_rate": 500,
			"current_travel": 100, "new_travel": 100,
			"current_housing": 200, "new_housing": 350,
			"current_safety": 0, "new_safety": 0,
			"current_shift": 0, "new_shift": 0,
			"current_phone": 0, "new_phone": 0,
			"current_opencast": 0, "new_opencast": 0,
		}
		rows = build_status_change_detail_rows(source)
		self.assertEqual(rows, [
			{"change_type": "Designation", "old_value": "Boilermaker", "new_value": "Fitter"},
			{"change_type": "Salary Component", "salary_component": "Housing Allowance",
			 "old_amount": 200.0, "new_amount": 350.0},
		])

	def _make_status_change_form(self, employee, new_designation, effective_date, **overrides):
		"""Defaults to a single Designation-change row (old_value gets
		auto-corrected to the employee's live designation by validate()
		regardless of what's passed here) - pass status_change_details
		explicitly to test Branch/Conditions of Employment/Salary Component
		rows instead, or a no-op employee: new_designation is then unused."""
		details = overrides.pop("status_change_details", None)
		if details is None:
			details = [{
				"change_type": "Designation",
				"old_value": employee.designation,
				"new_value": new_designation,
			}]

		values = {
			"doctype": "Status Change Form",
			"requested_by": employee.name,
			"employee": employee.name,
			"effective_date": effective_date,
			"reason": "ZZTEST status change reason",
			"status_change_details": details,
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Status Change Form", doc.name)
		return doc

	def test_validate_autopopulates_employee_and_requester_fields(self):
		company = get_reference_company()
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		branch = get_reference_branch()
		employee = self.make_employee(company=company, designation=current_designation, branch=branch)

		doc = self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 5)
		)

		self.assertEqual(doc.employee_name, employee.employee_name)
		self.assertEqual(doc.requested_by_name, employee.employee_name)
		self.assertEqual(doc.company, company)

		# current_designation/current_branch are no longer stored fields -
		# validate() auto-corrects the Designation row's old_value live from
		# the Employee record instead.
		details = doc.get("status_change_details") or []
		designation_rows = [d for d in details if d.change_type == "Designation"]
		self.assertEqual(len(designation_rows), 1)
		self.assertEqual(designation_rows[0].old_value, current_designation)
		self.assertEqual(designation_rows[0].new_value, new_designation)
		# _make_status_change_form's default row is Designation-only - no Branch row.
		self.assertFalse([d for d in details if d.change_type == "Branch"])

	def test_before_submit_requires_attach(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(designation=current_designation)
		doc = self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 5)
		)

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_on_submit_updates_employee_designation_and_history_when_changed(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		branch = frappe.db.get_value("Branch", {}, "name", order_by="creation asc")
		employee = self.make_employee(designation=current_designation, branch=branch)
		effective_date = add_days(getdate(nowdate()), 5)

		doc = self._make_status_change_form(
			employee, new_designation, effective_date, attach=DUMMY_ATTACH
		)
		doc.submit()

		employee.reload()
		self.assertEqual(employee.designation, new_designation)

		history = employee.get("internal_work_history") or []
		self.assertEqual(len(history), 2)

		closed_row, new_row = history[0], history[1]
		self.assertEqual(closed_row.designation, current_designation)
		self.assertEqual(closed_row.branch, branch)
		self.assertEqual(getdate(closed_row.to_date), effective_date)
		self.assertEqual(new_row.designation, new_designation)
		self.assertEqual(new_row.branch, branch)
		self.assertEqual(getdate(new_row.from_date), effective_date)
		self.assertFalse(new_row.to_date)

	def test_on_submit_updates_employee_branch_and_history_when_changed(self):
		current_designation = get_reference_designation()
		current_branch = get_reference_branch()
		new_branch = _second_branch(current_branch)
		employee = self.make_employee(designation=current_designation, branch=current_branch)
		effective_date = add_days(getdate(nowdate()), 5)

		# Only a Branch row - no Designation row - so only the branch is
		# changing here.
		doc = self._make_status_change_form(
			employee, current_designation, effective_date,
			status_change_details=[{
				"change_type": "Branch",
				"old_value": current_branch,
				"new_value": new_branch,
			}],
			attach=DUMMY_ATTACH,
		)
		doc.submit()

		employee.reload()
		self.assertEqual(employee.designation, current_designation)
		self.assertEqual(employee.branch, new_branch)

		history = employee.get("internal_work_history") or []
		self.assertEqual(len(history), 2)

		closed_row, new_row = history[0], history[1]
		self.assertEqual(closed_row.branch, current_branch)
		self.assertEqual(closed_row.designation, current_designation)
		self.assertEqual(getdate(closed_row.to_date), effective_date)
		self.assertEqual(new_row.branch, new_branch)
		self.assertEqual(new_row.designation, current_designation)
		self.assertEqual(getdate(new_row.from_date), effective_date)
		self.assertFalse(new_row.to_date)

	def test_on_submit_is_a_no_op_when_designation_and_branch_unchanged(self):
		current_designation = get_reference_designation()
		current_branch = get_reference_branch()
		employee = self.make_employee(designation=current_designation, branch=current_branch)
		effective_date = add_days(getdate(nowdate()), 5)

		# No Designation/Branch row at all - only an unrelated Salary
		# Component change - on_submit should be a true no-op for
		# Employee/internal_work_history.
		doc = self._make_status_change_form(
			employee, current_designation, effective_date,
			status_change_details=[{
				"change_type": "Salary Component",
				"salary_component": "Housing Allowance",
				"old_amount": 0,
				"new_amount": 500,
			}],
			attach=DUMMY_ATTACH,
		)
		doc.submit()

		employee.reload()
		self.assertEqual(employee.designation, current_designation)
		self.assertEqual(employee.branch, current_branch)
		self.assertEqual(employee.get("internal_work_history") or [], [])

	def test_duplicate_employee_designation_and_date_is_blocked(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(designation=current_designation)
		effective_date = add_days(getdate(nowdate()), 5)

		self._make_status_change_form(employee, new_designation, effective_date)

		with self.assertRaises(frappe.ValidationError):
			values = {
				"doctype": "Status Change Form",
				"requested_by": employee.name,
				"employee": employee.name,
				"effective_date": effective_date,
				"reason": "ZZTEST duplicate attempt",
				"status_change_details": [{
					"change_type": "Designation",
					"old_value": current_designation,
					"new_value": new_designation,
				}],
			}
			frappe.get_doc(values).insert(ignore_permissions=True)

	def test_second_form_with_different_date_is_allowed(self):
		current_designation = get_reference_designation()
		new_designation = _second_designation(current_designation)
		employee = self.make_employee(designation=current_designation)

		self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 5)
		)
		second = self._make_status_change_form(
			employee, new_designation, add_days(getdate(nowdate()), 6)
		)
		self.assertTrue(second.name)
