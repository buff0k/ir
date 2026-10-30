import frappe
from frappe.utils import add_days, today

from ir.ir_coida.doctype.oid_claim.oid_claim import OIDClaim
from za_local.tests.compat import UnitTestCase


class TestOIDClaim(UnitTestCase):
	def test_oid_claim_state_machine_rejects_reverse_transition(self):
		doc = frappe.new_doc("OID Claim")
		with self.assertRaises(frappe.ValidationError):
			OIDClaim._validate_transition(doc, "Approved", "Under Review")

	def test_oid_claim_parent_rejects_future_medical_report(self):
		doc = frappe.new_doc("OID Claim")
		doc.claim_status = "Submitted"
		doc.medical_reports = [
			frappe._dict(idx=1, report_date=add_days(today(), 1), report_type="Progress Report")
		]
		with self.assertRaises(frappe.ValidationError):
			OIDClaim.validate_medical_reports(doc)

	def test_oid_claim_rejects_dates_before_injury(self):
		doc = frappe.new_doc("OID Claim")
		doc.injury_date = "2026-04-10"
		doc.claim_date = "2026-04-09"

		with self.assertRaises(frappe.ValidationError):
			OIDClaim.validate_dates(doc)
