import json
from pathlib import Path
from unittest.mock import patch

import frappe

from ir.ir_payroll.doctype.irp5_certificate.irp5_certificate import (
	IRP5Certificate,
	build_certificate_key,
	require_certificate_generation_permissions,
)
from za_local.tests.compat import UnitTestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


class TestIRP5Certificate(UnitTestCase):
	def test_irp5_totals_follow_sars_4141_4149_and_4497_rules(self):
		doc = frappe.new_doc("IRP5 Certificate")
		doc.gross_taxable_income = 500_000
		doc.eti = 5_000
		for code, amount in (
			("4001", 60_000),
			("4102", 120_000),
			("4115", 1_000),
			("4116", 4_368),
			("4120", 500),
			("4141", 2_125),
		):
			doc.append("deduction_details", {"deduction_code": code, "amount": amount})
		for code, amount in (("4141", 2_125), ("4142", 6_000), ("4472", 10_000)):
			doc.append(
				"company_contribution_details",
				{"contribution_code": code, "amount": amount},
			)

		IRP5Certificate.calculate_totals(doc)

		self.assertEqual(121_000, doc.paye)
		self.assertEqual(4_250, doc.uif)
		self.assertEqual(6_000, doc.sdl)
		self.assertEqual(131_250, doc.total_tax_payable)
		self.assertEqual(70_000, doc.total_deductions_contributions)
		self.assertEqual(4_368, doc.medical_scheme_fees_tax_credit)
		self.assertEqual(500, doc.additional_medical_expenses_tax_credit)
		self.assertEqual("IRP5", doc.certificate_type)

	def test_zero_taxable_income_is_not_replaced_with_all_income(self):
		doc = frappe.new_doc("IRP5 Certificate")
		doc.gross_taxable_income = 0
		doc.non_taxable_income = 5_000
		doc.append("income_details", {"income_code": "3704", "amount": 5_000})

		IRP5Certificate.calculate_totals(doc)

		self.assertEqual(0, doc.gross_taxable_income)
		self.assertEqual("IT3(a)", doc.certificate_type)
		self.assertEqual("04", doc.reason_for_non_deduction)

	def test_reference_income_does_not_inflate_gross_taxable_income(self):
		doc = frappe.new_doc("IRP5 Certificate")
		doc.employee = "_Test Employee"
		doc.tax_year = "2026-2027"
		doc.reconciliation_period = "Final"
		doc.from_date = "2026-03-01"
		doc.to_date = "2027-02-28"
		salary_slip = frappe._dict(
			earnings=[
				frappe._dict(salary_component="Severance", amount=500_000),
				frappe._dict(salary_component="Basic", amount=300_000),
				frappe._dict(salary_component="Subsistence", amount=5_000),
			],
			deductions=[],
			company_contribution=[],
		)
		codes = {
			"Severance": frappe._dict(
				code="3901", description="Severance", category="Income", tax_treatment="Reference"
			),
			"Basic": frappe._dict(
				code="3601", description="Basic", category="Income", tax_treatment="Taxable"
			),
			"Subsistence": frappe._dict(
				code="3704", description="Subsistence", category="Income", tax_treatment="Non-Taxable"
			),
		}

		with (
			patch.object(IRP5Certificate, "_get_salary_slips", return_value=[frappe._dict(name="SS-1")]),
			patch("frappe.get_doc", return_value=salary_slip),
			patch.object(
				IRP5Certificate,
				"_get_sars_payroll_code",
				side_effect=lambda component: codes[component],
			),
		):
			IRP5Certificate._generate_certificate_lines(doc)

		self.assertEqual(300_000, doc.gross_taxable_income)
		self.assertEqual(5_000, doc.non_taxable_income)
		self.assertEqual({"3601", "3704", "3901"}, {row.income_code for row in doc.income_details})

	def test_taxable_it3a_requires_explicit_valid_reason_code(self):
		doc = frappe.new_doc("IRP5 Certificate")
		doc.gross_taxable_income = 50_000
		doc.certificate_type = "IRP5"
		IRP5Certificate.calculate_totals(doc)

		self.assertEqual("IT3(a)", doc.certificate_type)
		self.assertFalse(doc.reason_for_non_deduction)
		missing = IRP5Certificate.validate_statutory_readiness(doc, throw=False)
		self.assertIn("Valid SARS reason code 4150 (02-10)", missing)

		doc.reason_for_non_deduction = "02"
		missing = IRP5Certificate.validate_statutory_readiness(doc, throw=False)
		self.assertNotIn("Valid SARS reason code 4150 (02-10)", missing)

		doc.reason_for_non_deduction = "08"
		missing = IRP5Certificate.validate_statutory_readiness(doc, throw=False)
		self.assertIn("Reason code 08 requires medical tax credit code 4116 or 4120", missing)

	def test_taxable_it3a_below_threshold_gets_reason_code_02(self):
		doc = frappe.new_doc("IRP5 Certificate")
		doc.tax_year = "2026-2027"
		doc.date_of_birth = "1990-01-01"
		doc.gross_taxable_income = 36_000
		doc.periods_worked = 6
		doc.periods_in_year = 12

		IRP5Certificate.calculate_totals(doc)

		self.assertEqual("IT3(a)", doc.certificate_type)
		self.assertEqual("02", doc.reason_for_non_deduction)

	def test_certificate_key_is_canonical_across_certificate_type(self):
		irp5_key = build_certificate_key("_Test Company", "_Test Employee", "2026-2027", "Final")
		it3a_key = build_certificate_key("_Test Company", "_Test Employee", "2026-2027", "Final")
		self.assertEqual(irp5_key, it3a_key)

	def test_certificate_generation_requires_create_and_write_permissions(self):
		with (
			patch("frappe.has_permission", side_effect=[True, False]),
			self.assertRaises(frappe.PermissionError),
		):
			require_certificate_generation_permissions()

	def test_pay_period_snapshot_uses_frequency_and_deduplicates_off_cycle_slips(self):
		doc = frappe.new_doc("IRP5 Certificate")
		slips = [
			frappe._dict(
				name="SS-MAIN",
				end_date="2026-03-31",
				payroll_frequency="Monthly",
				total_working_days=22,
				payment_days=22,
			),
			frappe._dict(
				name="SS-OFFCYCLE",
				end_date="2026-03-20",
				payroll_frequency="Monthly",
				total_working_days=22,
				payment_days=5,
			),
		]

		IRP5Certificate._set_pay_period_snapshot(doc, slips)

		self.assertEqual(12, doc.periods_in_year)
		self.assertEqual(1, doc.periods_worked)

	def test_irp5_paye_total_includes_lump_sum_directive_tax(self):
		# IRP5 employees' tax must include ordinary PAYE (4102) AND lump-sum/directive
		# tax (4115), matching the EMP201 PAYE bucket so the EMP501 reconciles.
		doc = frappe.new_doc("IRP5 Certificate")
		doc.append("deduction_details", {"deduction_code": "4102", "amount": 100000})
		doc.append("deduction_details", {"deduction_code": "4115", "amount": 18000})
		doc.append("deduction_details", {"deduction_code": "4141", "amount": 2125.44})  # UIF, not PAYE
		IRP5Certificate.calculate_totals(doc)
		self.assertEqual(118000, doc.paye)
		self.assertEqual(2125.44, doc.uif)

	def test_irp5_eti_sums_actual_salary_slip_eti(self):
		# IRP5 ETI is the sum of the slips' za_monthly_eti (the same figure that flowed
		# to the EMP201) rather than an independent recomputation.
		doc = frappe.new_doc("IRP5 Certificate")
		doc.employee = "HR-EMP-RECON"
		doc.from_date = "2025-03-01"
		doc.to_date = "2026-02-28"
		slips = [frappe._dict(name=f"SS-{i:02d}") for i in range(12)]
		monthly_eti = {f"SS-{i:02d}": 500 for i in range(12)}
		with (
			patch.object(IRP5Certificate, "_get_salary_slips", return_value=slips),
			patch("frappe.db.get_value", side_effect=lambda dt, name, field: monthly_eti[name]),
		):
			IRP5Certificate.calculate_eti(doc)
		self.assertEqual(6000, doc.eti)

	def test_active_print_template_escapes_values_and_renders_required_fields(self):
		print_format = json.loads(
			(
				PACKAGE_ROOT
				/ "ir_payroll"
				/ "print_format"
				/ "irp5_employee_certificate"
				/ "irp5_employee_certificate.json"
			).read_text()
		)
		template = print_format["html"]
		self.assertIn('value if value is not none else "") | e', template)
		self.assertIn("Additional Medical Expenses Tax Credit", template)
		self.assertIn("Directive Number(s)", template)
		self.assertIn("Reason Code for IT3(a) (4150)", template)
		self.assertNotIn('field("ETI", money(doc.eti))', template)

		doc = frappe.new_doc("IRP5 Certificate")
		doc.employee_name = '<img src=x onerror="alert(1)">'
		doc.certificate_type = "IRP5"
		doc.set("income_details", [])
		doc.append(
			"income_details",
			{"income_code": "3601", "description": "<script>alert(1)</script>", "amount": 1},
		)
		rendered = frappe.render_template(template, {"doc": doc})
		self.assertIn("&lt;img", rendered)
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
		self.assertNotIn("<script>alert(1)</script>", rendered)

		it3_print_format = json.loads(
			(
				PACKAGE_ROOT
				/ "ir_payroll"
				/ "print_format"
				/ "irp5_it3_certificate"
				/ "irp5_it3_certificate.json"
			).read_text()
		)
		self.assertEqual(template, it3_print_format["html"])

		meta = json.loads(
			(PACKAGE_ROOT / "ir_payroll" / "doctype" / "irp5_certificate" / "irp5_certificate.json").read_text()
		)
		fields = {field["fieldname"]: field for field in meta["fields"]}
		self.assertEqual(1, fields["certificate_key"]["unique"])
		self.assertEqual("Float", fields["periods_in_year"]["fieldtype"])
		self.assertEqual("Float", fields["periods_worked"]["fieldtype"])
		self.assertEqual("IRP5 Certificate", fields["amended_from"]["options"])

		emp501_meta = json.loads(
			(
				PACKAGE_ROOT / "ir_payroll" / "doctype" / "emp501_reconciliation" / "emp501_reconciliation.json"
			).read_text()
		)
		emp501_fields = {field["fieldname"]: field for field in emp501_meta["fields"]}
		self.assertEqual("EMP501 Reconciliation", emp501_fields["amended_from"]["options"])
		self.assertNotIn("e_filing_csv", emp501_fields)

	def test_irp5_source_custom_fields_exist(self):
		checks = {
			"Employee": {
				"za_income_tax_reference_number",
				"za_residential_address",
				"za_postal_address",
				"za_business_address_override",
				"za_bank_account_type",
			},
			"Company": {
				"za_paye_reference_number",
				"za_trading_name",
				"za_business_address",
			},
			"Address": {
				"za_south_african_address_section",
				"za_unit_no",
				"za_postal_address_type",
				"za_address_line_4",
			},
			"Salary Component": {
				"za_sars_payroll_code",
			},
		}

		for doctype, expected_fields in checks.items():
			if not frappe.db.exists("DocType", doctype):
				continue

			meta = frappe.get_meta(doctype)
			fieldnames = {field.fieldname for field in meta.fields if field.fieldname}
			self.assertTrue(
				expected_fields.issubset(fieldnames),
				msg=f"Missing IRP5 source fields on {doctype}: {sorted(expected_fields - fieldnames)}",
			)

	def test_sars_payroll_codes_are_seeded(self):
		expected_codes = {"3601", "4102", "4116", "4118", "4142"}
		found_codes = set(
			frappe.get_all(
				"SARS Payroll Code",
				filters={"name": ["in", list(expected_codes)]},
				pluck="name",
			)
		)
		self.assertEqual(expected_codes, found_codes)

	def test_statutory_readiness_reports_missing_fields(self):
		doc = frappe.new_doc("IRP5 Certificate")
		doc.certificate_type = "IRP5"
		doc.company = "Test Company"
		doc.employee = "EMP-0001"
		doc.tax_year = "2026-2027"
		doc.from_date = "2026-03-01"
		doc.to_date = "2026-08-31"
		doc.reconciliation_period = "Interim"
		doc.gross_taxable_income = 1000

		missing = IRP5Certificate.validate_statutory_readiness(doc, throw=False)

		self.assertIn("Employer PAYE Reference Number", missing)
		self.assertIn("Employee income tax reference number", missing)
		self.assertIn("Residential address", missing)
		self.assertIn("Income line items", missing)

	def test_tax_certificate_select_fields_have_real_options(self):
		checks = {
			("Employee", "za_identity_type"): ["South African ID", "Passport", "Asylum Seeker"],
			("Employee", "za_nature_of_person"): ["Individual", "Director", "Foreign Employee"],
			("Employee", "za_bank_account_type"): ["Cheque", "Savings", "Other"],
			("Employee", "za_bank_account_holder_relationship"): ["Employee", "Spouse", "Other"],
			("Address", "za_postal_address_type"): ["Street", "PO Box", "Other"],
		}

		for (doctype, fieldname), expected_options in checks.items():
			field = frappe.get_meta(doctype).get_field(fieldname)
			self.assertIsNotNone(field, msg=f"Missing field {doctype}.{fieldname}")
			self.assertFalse(
				"\\n" in (field.options or ""),
				msg=f"{doctype}.{fieldname} still has escaped option separators",
			)
			options = [value for value in (field.options or "").split("\n") if value]
			for expected in expected_options:
				self.assertIn(expected, options, msg=f"{doctype}.{fieldname} missing option {expected}")
