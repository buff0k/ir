# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Repo-hygiene checks ported from za_local/tests/test_repo_hygiene.py as part
of absorbing za_local into ir - these three specifically read files that
moved to ir during that absorption (public/js/payroll_entry.js, public/js/
salary_structure.js, and the whole practitioner_guide package). The CSS half
of the flexible-benefit check still reads za_local's own public/css/
za_local.css, which has not moved - that file is still genuinely za_local's
own, loaded site-wide via its own app_include_css.
"""

import json
import re
import unittest
from pathlib import Path

import frappe

APP_ROOT = Path(__file__).resolve().parents[1]


class TestRepositoryHygiene(unittest.TestCase):
	def test_payroll_dialog_uses_dom_text_for_employee_values(self):
		text = (APP_ROOT / "public" / "js" / "payroll_entry.js").read_text()
		self.assertNotIn("${row.employee_name}", text)
		self.assertIn('.text(`${row.employee}: ${row.employee_name || ""}`)', text)
		self.assertIn("encodeURIComponent(row.employee)", text)

	def test_flexible_benefit_hiding_never_targets_shared_form_sections(self):
		css_path = Path(frappe.get_app_path("za_local")) / "public" / "css" / "za_local.css"
		css = css_path.read_text()
		javascript = (APP_ROOT / "public" / "js" / "salary_structure.js").read_text()
		css_rules = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

		self.assertNotRegex(css_rules, r"\.form-section[^\{]*max_benefits")
		self.assertNotIn("za-hidden-flexible-benefits", css + javascript)
		self.assertNotIn("closest('.form-section')", javascript)
		self.assertIn("frm.toggle_display(fieldname, false)", javascript)

	def test_practitioner_guide_manifest_matches_content(self):
		from ir.practitioner_guide.manifest import GUIDES

		content_dir = APP_ROOT / "practitioner_guide" / "content"
		pages = [
			(guide["space"]["route"], group["key"], page)
			for guide in GUIDES
			for group in guide["groups"]
			for page in group["pages"]
		]
		files = [page["file"] for _, _, page in pages]
		routes = [f"{space}/{group}/{page['slug']}" for space, group, page in pages]
		content_files = sorted(path.name for path in content_dir.glob("*.md"))

		self.assertEqual(len(files), len(set(files)), "Guide content files must be referenced once")
		self.assertEqual(len(routes), len(set(routes)), "Guide routes must be unique")
		self.assertEqual(sorted(files), content_files, "Manifest and guide content files must match")

	def test_sa_print_formats_are_file_scoped(self):
		expected = {
			"ir_vat/print_format/sa_sales_invoice/sa_sales_invoice.json": "SA Sales Invoice",
			"ir_vat/print_format/sa_full_tax_invoice/sa_full_tax_invoice.json": "SA Full Tax Invoice",
			"ir_vat/print_format/sa_abridged_tax_invoice/sa_abridged_tax_invoice.json": "SA Abridged Tax Invoice",
			"ir_vat/print_format/sa_sales_order/sa_sales_order.json": "SA Sales Order",
			"ir_vat/print_format/sa_quotation/sa_quotation.json": "SA Quotation",
			"ir_vat/print_format/sa_delivery_note/sa_delivery_note.json": "SA Delivery Note",
			"ir_vat/print_format/sa_purchase_invoice/sa_purchase_invoice.json": "SA Purchase Invoice",
			"ir_vat/print_format/sa_purchase_order/sa_purchase_order.json": "SA Purchase Order",
			"ir_vat/print_format/sa_credit_note/sa_credit_note.json": "SA Credit Note",
			"ir_vat/print_format/sa_debit_note/sa_debit_note.json": "SA Debit Note",
			"ir_vat/print_format/sa_payment_entry/sa_payment_entry.json": "SA Payment Entry",
			"ir_payroll/print_format/irp5_employee_certificate/irp5_employee_certificate.json": "IRP5 Employee Certificate",
			"ir_payroll/print_format/irp5_it3_certificate/irp5_it3_certificate.json": "IRP5-it3 Certificate",
			"ir_payroll/print_format/sa_salary_slip/sa_salary_slip.json": "SA Salary Slip",
		}

		for relative_path, name in expected.items():
			path = APP_ROOT / relative_path
			self.assertTrue(path.exists(), msg=f"Missing print format JSON: {relative_path}")
			with path.open() as handle:
				data = json.load(handle)

			self.assertEqual(data.get("name"), name)
			self.assertEqual(data.get("doctype"), "Print Format")
			self.assertEqual(data.get("print_format_for"), "DocType")
			self.assertEqual(data.get("print_format_type"), "Jinja")
			self.assertEqual(data.get("standard"), "Yes")
			if relative_path.startswith("ir_vat/print_format/"):
				self.assertIn(
					"{% include",
					data.get("html") or "",
					msg=f"{name} should use the shared, null-safe commercial template",
				)

	def test_expected_sa_module_onboarding_exists(self):
		expected = {
			"ir_setup/module_onboarding/sa_localisation_onboarding/sa_localisation_onboarding.json",
			"ir_setup/module_onboarding/sa_overview_onboarding/sa_overview_onboarding.json",
			"ir_vat/module_onboarding/sa_vat_onboarding/sa_vat_onboarding.json",
			"ir_payroll/module_onboarding/sa_payroll_onboarding/sa_payroll_onboarding.json",
			"ir_labour/module_onboarding/sa_labour_onboarding/sa_labour_onboarding.json",
			"ir_coida/module_onboarding/sa_coida_onboarding/sa_coida_onboarding.json",
		}
		missing = [relative for relative in expected if not (APP_ROOT / relative).exists()]
		self.assertFalse(missing, msg=f"Missing expected module onboarding standard docs: {missing}")
