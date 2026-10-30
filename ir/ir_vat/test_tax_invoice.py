import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from ir.ir_vat.report.vat_201_account_classifications import vat_201_account_classifications
from ir.ir_vat.report.vat_201_linked_transactions import vat_201_linked_transactions
from ir.ir_vat.setup import validate_vat_posting_account
from ir.ir_vat.tax_invoice import (
	build_sales_invoice_print_profile,
	check_tax_invoice_readiness,
	get_sales_invoice_print_profile,
)
from ir.tests.compat import UnitTestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class TestTaxInvoiceReadiness(UnitTestCase):
	def test_non_zar_threshold_is_conservative_and_returns_use_credit_note(self):
		with patch("ir.ir_vat.tax_invoice.is_company_in_south_africa", return_value=True):
			profile = build_sales_invoice_print_profile(
				company="Test Company",
				base_grand_total=100,
				company_currency="USD",
			)
			credit = build_sales_invoice_print_profile(
				company="Test Company",
				base_grand_total=-5750,
				is_return=1,
				company_currency="ZAR",
			)

		self.assertEqual("full_tax_invoice", profile["invoice_type"])
		self.assertEqual("conservative_non_zar_company_currency", profile["threshold_basis"])
		self.assertEqual("credit_note", credit["invoice_type"])
		self.assertEqual("SA Credit Note", credit["print_format"])

	def test_abridged_readiness_does_not_require_recipient_details(self):
		invoice = SimpleNamespace(
			name="SINV-TEST",
			company="Test Company",
			base_grand_total=115,
			grand_total=115,
			is_pos=0,
			is_return=0,
			company_address_display="1 Test Street",
			company_tax_id="4123456789",
			customer=None,
			customer_name=None,
			address_display=None,
			posting_date="2026-04-10",
			items=[SimpleNamespace(description="Service", qty=1)],
			total_taxes_and_charges=15,
		)
		with (
			patch("ir.ir_vat.tax_invoice.frappe.get_doc", return_value=invoice),
			patch("ir.ir_vat.tax_invoice.get_company_vat_registration_number", return_value="4123456789"),
			patch("ir.ir_vat.tax_invoice.get_company_currency", return_value="ZAR"),
			patch("ir.ir_vat.tax_invoice.is_company_in_south_africa", return_value=True),
		):
			result = check_tax_invoice_readiness("SINV-TEST")

		self.assertEqual("ready", result["status"])
		self.assertNotIn("Recipient name", result["missing"])
		self.assertNotIn("Recipient address", result["missing"])

	def test_print_profile_endpoint_checks_invoice_and_company_permissions(self):
		with (
			patch("ir.ir_vat.tax_invoice.frappe.has_permission") as has_permission,
			patch("ir.ir_vat.tax_invoice.get_company_currency", return_value="ZAR"),
			patch("ir.ir_vat.tax_invoice.is_company_in_south_africa", return_value=True),
		):
			get_sales_invoice_print_profile(company="Test Company", base_grand_total=115)

		has_permission.assert_any_call("Sales Invoice", "read", throw=True)
		has_permission.assert_any_call("Company", "read", "Test Company", throw=True)

	def test_tax_invoice_readiness_loads_with_permission_check(self):
		invoice = SimpleNamespace(
			name="SINV-TEST",
			company="Test Company",
			base_grand_total=100,
			grand_total=100,
			is_pos=0,
			is_return=0,
			company_address_display="1 Test Street",
			company_tax_id="4123456789",
			customer_name="Test Customer",
			address_display="2 Test Street",
			posting_date="2026-04-10",
			items=[SimpleNamespace(description="Service", qty=1)],
			total_taxes_and_charges=15,
		)
		with (
			patch("ir.ir_vat.tax_invoice.frappe.get_doc", return_value=invoice) as get_doc,
			patch("ir.ir_vat.tax_invoice.get_company_vat_registration_number", return_value="4123456789"),
			patch("ir.ir_vat.tax_invoice.get_company_currency", return_value="ZAR"),
			patch("ir.ir_vat.tax_invoice.is_company_in_south_africa", return_value=True),
		):
			check_tax_invoice_readiness("SINV-TEST")

		get_doc.assert_called_once_with("Sales Invoice", "SINV-TEST", check_permission=True)


class TestVATSetupAndReports(UnitTestCase):
	def test_vat_posting_accounts_must_be_enabled_tax_ledgers_for_the_company(self):
		with patch(
			"ir.ir_vat.setup.frappe.db.get_value",
			return_value=frappe._dict(company="Test Company", account_type="Tax", is_group=0, disabled=0),
		):
			validate_vat_posting_account("VAT Output - TC", "Test Company", "Output VAT Account")

	def test_vat_bootstrap_stops_before_writes_without_system_manager_role(self):
		from ir.ir_vat.setup import bootstrap_company_vat_setup

		with (
			patch(
				"ir.ir_vat.setup.frappe.only_for",
				side_effect=frappe.PermissionError("Not permitted"),
			),
			patch("ir.ir_vat.setup.get_vat_settings") as get_settings,
		):
			with self.assertRaises(frappe.PermissionError):
				bootstrap_company_vat_setup("Test Company")

		get_settings.assert_not_called()

	def test_linked_report_authorizes_parent_before_reading_child_rows(self):
		with (
			patch("ir.ir_vat.report.vat_201_linked_transactions.vat_201_linked_transactions.frappe.get_doc") as get_doc,
			patch(
				"ir.ir_vat.report.vat_201_linked_transactions.vat_201_linked_transactions.frappe.get_all",
				return_value=[],
			),
		):
			vat_201_linked_transactions.get_data({"vat_return": "VAT201-TEST"})

		get_doc.assert_called_once_with("VAT201 Return", "VAT201-TEST", check_permission=True)

	def test_account_classification_report_uses_permission_filtered_list(self):
		with (
			patch(
				"ir.ir_vat.report.vat_201_account_classifications.vat_201_account_classifications.frappe.has_permission"
			) as has_permission,
			patch(
				"ir.ir_vat.report.vat_201_account_classifications.vat_201_account_classifications.frappe.get_list",
				return_value=[],
			) as get_list,
		):
			vat_201_account_classifications.execute({"company": "Test Company"})

		has_permission.assert_called_once_with("Account", "read", throw=True)
		self.assertEqual("Account", get_list.call_args.args[0])

	def test_vat_print_formats_use_shared_templates(self):
		for path in (PACKAGE_ROOT / "ir_vat" / "print_format").glob("*/sa_*.json"):
			data = json.loads(path.read_text())
			if data["name"] == "SA VAT201 Return":
				continue
			self.assertIn("{% include", data["html"], msg=data["name"])
			self.assertLess(len(data["html"].splitlines()), 10, msg=data["name"])

		template = (PACKAGE_ROOT / "templates" / "print_format" / "sa_commercial_document.html").read_text()
		self.assertIn("{% if address %}", template)
		self.assertNotIn("amount > 5000", template)
