# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Backfill the ETI unregulated-minimum-wage Payroll Settings default.

Ported from za_local.sa_setup.install.ensure_eti_payroll_settings_defaults
as part of absorbing za_local into ir - that function ran unconditionally
on every install/migrate even though it is a one-time default backfill,
not a recurring task.
"""

import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.exists("DocType", "Payroll Settings"):
		return
	fieldname = "za_eti_unregulated_minimum_monthly_wage"
	if not frappe.get_meta("Payroll Settings").has_field(fieldname):
		return
	if not flt(frappe.db.get_single_value("Payroll Settings", fieldname)):
		frappe.db.set_single_value("Payroll Settings", fieldname, 2500)
	frappe.db.commit()
