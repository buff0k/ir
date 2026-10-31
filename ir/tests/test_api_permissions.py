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
