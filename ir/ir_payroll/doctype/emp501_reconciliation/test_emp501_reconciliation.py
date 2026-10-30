from unittest.mock import patch

import frappe

from ir.ir_payroll.doctype.emp501_reconciliation.emp501_reconciliation import EMP501Reconciliation
from ir.utils.emp501_utils import generate_emp501_csv
from ir.tests.compat import UnitTestCase


class TestEMP501Reconciliation(UnitTestCase):
	def test_emp501_requires_complete_emp201_coverage(self):
		doc = frappe.new_doc("EMP501 Reconciliation")
		doc.company = "Test Company"
		doc.tax_year = "2026-2027"
		doc.reconciliation_period = "Interim"
		doc.from_date = "2026-03-01"
		doc.to_date = "2026-08-31"

		with patch(
			"frappe.get_all",
			return_value=[
				frappe._dict(name="EMP201-03", submission_period_start_date="2026-03-01"),
				frappe._dict(name="EMP201-04", submission_period_start_date="2026-04-01"),
			],
		):
			result = EMP501Reconciliation.validate_emp201_period_coverage(doc, throw=False)

		self.assertEqual(
			["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"],
			[str(value) for value in result["missing_periods"]],
		)

	def test_emp501_reconciles_certificates_to_generated_not_utilized_eti(self):
		doc = frappe.new_doc("EMP501 Reconciliation")
		rows = [
			frappe._dict(
				name="EMP201-MAR",
				submission_period_start_date="2026-03-01",
				gross_paye_before_eti=1_000,
				uif_payable=100,
				sdl_payable=50,
				eti_carried_forward_from_previous=100,
				eti_generated_current_month=300,
				eti_utilized_current_month=250,
				eti_to_be_carried_forward=150,
			),
			frappe._dict(
				name="EMP201-APR",
				submission_period_start_date="2026-04-01",
				gross_paye_before_eti=1_200,
				uif_payable=120,
				sdl_payable=60,
				eti_carried_forward_from_previous=150,
				eti_generated_current_month=200,
				eti_utilized_current_month=250,
				eti_to_be_carried_forward=100,
			),
		]
		certificate_totals = frappe._dict(paye=2_200, uif=220, sdl=110, eti=500)

		with patch.object(EMP501Reconciliation, "_get_linked_emp201_rows", return_value=rows):
			result = EMP501Reconciliation.validate_certificate_reconciliation(
				doc,
				certificate_totals,
			)

		self.assertEqual(500, result.eti_generated)
		self.assertEqual(500, result.eti_utilized)

		certificate_totals.eti = 400
		with (
			patch.object(EMP501Reconciliation, "_get_linked_emp201_rows", return_value=rows),
			self.assertRaises(frappe.ValidationError),
		):
			EMP501Reconciliation.validate_certificate_reconciliation(doc, certificate_totals)

	def test_emp501_coverage_rejects_draft_certificate(self):
		doc = frappe.new_doc("EMP501 Reconciliation")
		doc.append(
			"irp5_certificates",
			{
				"employee": "_Test Employee",
				"employee_name": "_Test Employee",
				"irp5_certificate": "IRP5-DRAFT",
			},
		)
		with (
			patch.object(
				EMP501Reconciliation,
				"_get_salary_slip_employees",
				return_value={"_Test Employee": "_Test Employee"},
			),
			patch(
				"frappe.get_all",
				return_value=[
					frappe._dict(
						name="IRP5-DRAFT",
						employee="_Test Employee",
						company=None,
						tax_year=None,
						reconciliation_period=None,
						from_date=None,
						to_date=None,
						docstatus=0,
						status="Prepared",
					)
				],
			),
			self.assertRaises(frappe.ValidationError),
		):
			EMP501Reconciliation.validate_irp5_coverage(doc)

	def test_emp501_linked_emp201_rows_must_match_period_coverage(self):
		doc = frappe.new_doc("EMP501 Reconciliation")
		doc.append("emp201_submissions", {"emp201_submission": "EMP201-MAR"})
		coverage = {
			"missing_periods": [],
			"duplicate_periods": [],
			"linked_submissions": [frappe._dict(name="EMP201-MAR"), frappe._dict(name="EMP201-APR")],
		}
		with (
			patch.object(EMP501Reconciliation, "validate_emp201_period_coverage", return_value=coverage),
			patch.object(
				EMP501Reconciliation,
				"_get_linked_emp201_rows",
				return_value=[frappe._dict(name="EMP201-MAR")],
			),
			self.assertRaises(frappe.ValidationError),
		):
			EMP501Reconciliation.validate_linked_emp201_references(doc)

	def test_emp501_totals_use_gross_paye_and_reconcile_to_irp5(self):
		# EMP501 payable uses ETI utilised. Certificate code 4118 is reconciled
		# separately to EMP201 ETI generated (the theoretical amount).
		emp501 = frappe.new_doc("EMP501 Reconciliation")
		emp501.append("emp201_submissions", {"emp201_submission": "EMP201-RECON"})
		emp201 = [
			frappe._dict(
				name="EMP201-RECON",
				submission_period_start_date="2026-03-01",
				gross_paye_before_eti=118000.0,  # 4102 (100000) + 4115 (18000)
				sdl_payable=41470.0,
				uif_payable=18323.52,
				eti_utilized_current_month=5000.0,
				eti_generated_current_month=6000.0,
				eti_carried_forward_from_previous=0,
				eti_to_be_carried_forward=1000,
			)
		]
		with patch.object(EMP501Reconciliation, "_get_linked_emp201_rows", return_value=emp201):
			EMP501Reconciliation.calculate_totals(emp501)

		# Gross basis (not the net 112000)
		self.assertEqual(118000.0, emp501.total_paye)
		self.assertEqual(5000.0, emp501.total_eti)

		# PAYE ties directly; ETI 4118 ties to generated, not utilised.
		irp5_paye_total = 100000 + 18000  # IRP5 paye sums {4102, 4115}
		irp5_eti_total = 6000  # IRP5 eti sums slip za_monthly_eti
		self.assertEqual(emp501.total_paye, irp5_paye_total)
		self.assertEqual(emp201[0].eti_generated_current_month, irp5_eti_total)

	def test_emp501_submission_readiness_requires_sars_references(self):
		doc = frappe.new_doc("EMP501 Reconciliation")
		doc.paye_reference_number = ""
		doc.sdl_reference_number = "L123456789"
		doc.uif_reference_number = ""

		with self.assertRaises(frappe.ValidationError):
			EMP501Reconciliation.validate_submission_readiness(doc)

	def test_invalid_mixed_record_csv_is_retired(self):
		with (
			patch("frappe.get_doc"),
			patch("frappe.has_permission", return_value=True),
			self.assertRaisesRegex(frappe.ValidationError, "legacy mixed-record CSV was removed"),
		):
			generate_emp501_csv("_Test EMP501")
