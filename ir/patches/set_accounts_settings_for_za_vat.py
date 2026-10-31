# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Configure Accounts Settings so SA VAT tax rows come from document
templates only.

- add_taxes_from_taxes_and_charges_template = 1: Sales/Purchase Templates
  define tax rows (VAT Collected / VAT Paid).
- add_taxes_from_item_tax_template = 0: Item templates only affect rate per
  item, not which accounts appear.

This prevents VAT Collected (sales) from appearing on Purchase Invoices
when items have a Sales-oriented template.

Ported from za_local.sa_setup.install.set_accounts_settings_for_za_vat as
part of absorbing za_local into ir - that function ran only from
after_install, so sites that installed za_local before this setting
existed, or that migrate straight to the absorbed version, never got it.

Note: the original also guarded on frappe.db.table_exists("Accounts
Settings"), but Accounts Settings is a Single doctype with no tab<DocType>
table of its own (all Single values live in tabSingles) - that guard was
always False, so the original function was a silent no-op. Fixed here to
check the DocType's existence instead.

The real logic lives in ir.ir_setup.install.ensure_accounts_settings_for_za_vat
so the ZA Local Setup wizard (ir.ir_setup.install.run_za_local_setup) can
also call it, rather than duplicating it.
"""

import frappe


def execute():
	from ir.ir_setup.install import ensure_accounts_settings_for_za_vat

	ensure_accounts_settings_for_za_vat()
	frappe.db.commit()
