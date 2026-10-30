import json
from pathlib import Path
from types import SimpleNamespace

import frappe

from ir.ir_vat.doctype.vat201_return.vat201_return import VAT201Return
from za_local.tests.compat import UnitTestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


class TestVAT201Return(UnitTestCase):
	def test_return_sign_is_not_inverted_twice(self):
		worker = SimpleNamespace()
		self.assertEqual(1, VAT201Return.get_invoice_sign(worker, frappe._dict(is_return=1, base_net_total=-100)))
		self.assertEqual(-1, VAT201Return.get_invoice_sign(worker, frappe._dict(is_return=1, base_net_total=100)))

	def test_vat201_allocation_uses_vat_inclusive_consideration_and_reversal_side(self):
		worker = SimpleNamespace(make_transaction_row=lambda **values: values)
		invoice = frappe._dict(name="SINV-TEST", posting_date="2026-04-10")
		rows = VAT201Return.allocate_tax_by_group(
			worker,
			invoice,
			{"Output - A Standard rate (excl capital goods)": 100},
			15,
			"SA Standard Rated Sales 15% - Test Company",
		)
		reversal = VAT201Return.allocate_tax_by_group(
			worker,
			invoice,
			{"Output - A Standard rate (excl capital goods)": -100},
			-15,
			"SA Standard Rated Sales 15% - Test Company",
		)

		self.assertEqual(115, rows[0]["incl_tax_amount"])
		self.assertEqual(15, rows[0]["tax_account_credit"])
		self.assertEqual(-115, reversal[0]["incl_tax_amount"])
		self.assertEqual(15, reversal[0]["tax_account_debit"])

	def test_vat201_doctype_supports_submit_cancel_and_amend(self):
		path = PACKAGE_ROOT / "ir_vat" / "doctype" / "vat201_return" / "vat201_return.json"
		data = json.loads(path.read_text())
		self.assertEqual(1, data["is_submittable"])
		for role in ("System Manager", "Accounts Manager"):
			permissions = next(row for row in data["permissions"] if row["role"] == role)
			self.assertEqual(1, permissions["submit"])
			self.assertEqual(1, permissions["cancel"])
			self.assertEqual(1, permissions["amend"])
