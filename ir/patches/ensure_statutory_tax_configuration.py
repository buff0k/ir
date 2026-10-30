# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Backfill missing company-scoped South African payroll tax masters.

Ported from za_local.patches.v1_1.ensure_statutory_tax_configuration as
part of absorbing za_local into ir - this now also runs as part of ir's
own after_migrate (ir.ir_setup.install.ensure_all_company_tax_configuration),
so this patch mainly matters for sites that migrate straight to the
absorbed version without ever having run za_local's original patch.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Company"):
		return

	from ir.ir_setup.install import ensure_all_company_tax_configuration

	ensure_all_company_tax_configuration()
