# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Shared synthetic-data helpers for ir functional tests.

This bench has no dedicated test site - these tests run against the live
eben.isambane.co.za site. Every record created here must be unmistakably
synthetic (SYNTHETIC_PREFIX) and fully cleaned up afterward.
IRSyntheticDataTestCase tracks everything created via track()/make_employee()
and deletes it in reverse order in tearDown(), with an explicit
frappe.db.commit() - Frappe's own test-record machinery already commits as
it creates records (frappe/tests/utils/generators.py), so a bare rollback
cannot be relied on to undo it; cleanup must actually commit too.
"""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_years, getdate, nowdate

SYNTHETIC_PREFIX = "ZZTEST"


def synthetic_suffix() -> str:
	return frappe.generate_hash(length=8)


def synthetic_name(label: str = "") -> str:
	suffix = synthetic_suffix()
	return f"{SYNTHETIC_PREFIX}-{label}-{suffix}" if label else f"{SYNTHETIC_PREFIX}-{suffix}"


def get_reference_company() -> str:
	"""An existing, real Company to parent synthetic test data under -
	deliberately not a fake Company, since Company creation in ERPNext
	cascades into a default Cost Center/Warehouse/CoA that would be much
	harder to fully unwind on a live site than a same-company Employee."""
	company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	if not company:
		frappe.throw("No Company exists on this site - cannot build synthetic test fixtures.")
	return company


def get_reference_branch() -> str | None:
	return frappe.db.get_value("Branch", {}, "name", order_by="creation asc")


def get_reference_designation() -> str | None:
	return frappe.db.get_value("Designation", {}, "name", order_by="creation asc")


class IRSyntheticDataTestCase(IntegrationTestCase):
	"""Base class for ir functional tests that create real DB rows on the
	live site. Use make_employee()/track() rather than raw frappe.get_doc()
	so every created row is guaranteed to be cleaned up, even on failure."""

	def setUp(self):
		super().setUp()
		self._ir_test_docs: list[tuple[str, str]] = []

	def tearDown(self):
		self._cleanup_tracked_docs()
		super().tearDown()

	def track(self, doctype: str, name: str) -> None:
		"""Register a doc for cleanup. Call in creation order - cleanup
		runs in reverse, so dependents are removed before what they link to."""
		self._ir_test_docs.append((doctype, name))

	def _cleanup_tracked_docs(self) -> None:
		for doctype, name in reversed(self._ir_test_docs):
			try:
				if not frappe.db.exists(doctype, name):
					continue
				meta = frappe.get_meta(doctype)
				if meta.is_submittable:
					docstatus = frappe.db.get_value(doctype, name, "docstatus")
					if docstatus == 1:
						doc = frappe.get_doc(doctype, name)
						doc.flags.ignore_permissions = True
						doc.cancel()
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, ignore_missing=True)
			except Exception:
				frappe.log_error(title=f"ir test cleanup failed for {doctype} {name}")
		frappe.db.commit()

	def make_employee(self, **overrides) -> "frappe.model.document.Document":
		company = overrides.pop("company", None) or get_reference_company()
		suffix = synthetic_suffix()
		values = {
			"doctype": "Employee",
			"first_name": overrides.pop("first_name", SYNTHETIC_PREFIX),
			"last_name": overrides.pop("last_name", suffix),
			"employee_number": overrides.pop("employee_number", f"{SYNTHETIC_PREFIX}-{suffix}"),
			"gender": overrides.pop("gender", "Male"),
			"date_of_birth": overrides.pop("date_of_birth", add_years(getdate(nowdate()), -30)),
			"date_of_joining": overrides.pop("date_of_joining", add_years(getdate(nowdate()), -5)),
			"status": overrides.pop("status", "Active"),
			"company": company,
		}
		values.update(overrides)

		employee = frappe.get_doc(values)
		employee.insert(ignore_permissions=True)
		self.track("Employee", employee.name)
		return employee

	def make_retrenchment_process(self, employees=None, num_employees=2, **overrides):
		"""Build a synthetic Retrenchment Process with Affected Employee rows -
		the shared fixture reused (freshly, per test) by Retrenchment Process's
		own tests as well as Section 189 Notice / S189 Consultation, both of
		which link to a Retrenchment Process via `linked_intervention`. Pass
		`employees` (a list of already-created Employee docs) to reuse specific
		employees, or leave it to synthesize `num_employees` fresh ones."""
		company = overrides.pop("company", None) or get_reference_company()
		branch = overrides.pop("branch", None) or get_reference_branch()
		designation = overrides.pop("designation", None) or get_reference_designation()
		affected_employees = overrides.pop("affected_employees", None)

		if affected_employees is None:
			if employees is None:
				employees = [self.make_employee(company=company) for _ in range(num_employees)]
			affected_employees = [
				{"branch": branch, "designation": designation, "employee": employee.name}
				for employee in employees
			]

		values = {
			"doctype": "Retrenchment Process",
			"process_title": synthetic_name("Retrenchment"),
			"company": company,
			"process_type": "Section 189",
			"reason_for_dismissals": overrides.pop("reason_for_dismissals", "ZZTEST operational requirements"),
			"selection_method": overrides.pop("selection_method", "ZZTEST LIFO by date of joining"),
			"affected_employees": affected_employees,
		}
		values.update(overrides)

		process = frappe.get_doc(values)
		process.insert(ignore_permissions=True)
		self.track("Retrenchment Process", process.name)
		return process
