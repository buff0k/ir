# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Cross-cutting whitelisted-endpoint permission/HTTP-method regression tests.

Ported from za_local/tests/test_api_permissions.py and test_statutory_
workflow_regressions.py as part of absorbing za_local into ir - these span
several unrelated modules (ir_vat.setup, overrides.payroll_entry,
overrides.journal_entry, utils.integrations.eft_file_generator, print
format registration across every absorbed module) rather than belonging
to one doctype.
"""

import json
from pathlib import Path
from unittest.mock import patch

import frappe

from ir.tests.compat import UnitTestCase


class TestWhitelistedEndpointPermissions(UnitTestCase):
	def test_state_changing_endpoints_accept_post_only(self):
		from ir.ir_vat.setup import bootstrap_company_vat_setup
		from ir.overrides.journal_entry import (
			force_delete_all_cancelled_payroll_journal_entries,
			force_delete_cancelled_payroll_journal_entry,
		)
		from ir.overrides.payroll_entry import make_payment_entry_for_payroll
		from ir.utils.integrations.eft_file_generator import generate_eft_file

		for method in (
			bootstrap_company_vat_setup,
			make_payment_entry_for_payroll,
			generate_eft_file,
			force_delete_all_cancelled_payroll_journal_entries,
			force_delete_cancelled_payroll_journal_entry,
		):
			self.assertEqual(
				frappe.allowed_http_methods_for_whitelisted_func[method],
				["POST"],
			)

	def test_payroll_payment_wrapper_denies_read_only_user_before_loading_document(self):
		from ir.overrides.payroll_entry import make_payment_entry_for_payroll

		with (
			patch("ir.overrides.payroll_entry.frappe.db.exists", return_value=True),
			patch("ir.overrides.payroll_entry.frappe.has_permission", return_value=False),
			patch("ir.overrides.payroll_entry.frappe.get_doc") as get_doc,
		):
			with self.assertRaises(frappe.PermissionError):
				make_payment_entry_for_payroll("Payroll Entry", "PAY-TEST")

		get_doc.assert_not_called()

	def test_eft_export_requires_payroll_role_before_reading_banking_data(self):
		from ir.utils.integrations.eft_file_generator import generate_eft_file

		with (
			patch(
				"ir.utils.integrations.eft_file_generator.frappe.only_for",
				side_effect=frappe.PermissionError("Not permitted"),
			),
			patch(
				"ir.utils.integrations.eft_file_generator.frappe.has_permission"
			) as has_permission,
		):
			with self.assertRaises(frappe.PermissionError):
				generate_eft_file("PAY-TEST")

		has_permission.assert_not_called()


class TestStatusChangeFormDesignationRestriction(UnitTestCase):
	"""Status Change Form stopped storing its own current_designation
	snapshot once the Status Change Detail child table took over - without
	this, Designation Limits would silently stop applying to every record
	created after that field went away (current_designation would just be
	NULL, and `bool(None) and ...` reads as "not restricted"). permissions.py
	must resolve its "relevant designation" live via the linked Employee
	instead - see DESIGNATION_VIA_EMPLOYEE_DOCTYPES."""

	def test_root_case_fields_resolves_designation_via_employee(self):
		from ir.permissions import _root_case_fields

		with patch("ir.permissions.frappe.db.get_value", return_value="ZZTEST Designation") as get_value:
			doc = frappe._dict({"doctype": "Status Change Form", "employee": "ZZTEST-0001"})
			employee, designation = _root_case_fields(doc)

		self.assertEqual(employee, "ZZTEST-0001")
		self.assertEqual(designation, "ZZTEST Designation")
		get_value.assert_called_once_with("Employee", "ZZTEST-0001", "designation")

	def test_root_case_fields_no_employee_resolves_no_designation(self):
		from ir.permissions import _root_case_fields

		doc = frappe._dict({"doctype": "Status Change Form", "employee": None})
		employee, designation = _root_case_fields(doc)

		self.assertIsNone(employee)
		self.assertIsNone(designation)

	def test_permission_query_designation_condition_is_a_live_employee_subquery(self):
		from ir.permissions import _permission_query

		with (
			patch("ir.permissions.restricted_designations_for_user", return_value=["ZZTEST Designation"]),
			patch("ir.permissions.responsible_branches_for_user", return_value=[]),
			patch("ir.permissions.effective_ir_role", return_value="IR Officer"),
			patch("ir.permissions._sql_responsible_ir_override", return_value=None),
		):
			condition = _permission_query("Status Change Form", "test@example.com")

		self.assertIn("SELECT designation FROM `tabEmployee`", condition)
		self.assertIn("`tabStatus Change Form`.`employee`", condition)
		self.assertNotIn("current_designation", condition)


class TestPrintFormatRegistration(UnitTestCase):
	def test_sa_print_format_json_has_inline_html_and_no_legacy_app_references(self):
		app_root = Path(frappe.get_app_path("ir"))
		json_files = list(app_root.glob("ir_vat/print_format/*/*.json")) + list(
			app_root.glob("ir_payroll/print_format/*/*.json")
		)
		self.assertTrue(json_files, msg="No standard print format JSON files found")

		for path in json_files:
			payload = json.loads(path.read_text())
			html = payload.get("html") or ""
			self.assertTrue(html.strip(), msg=f"{path} must store inline Jinja HTML")
			self.assertNotIn("erpnext_south_africa", html)
			self.assertNotIn("kartoza", html.lower())
