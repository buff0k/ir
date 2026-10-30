# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Backfill database-enforced identities for EMP201 declaration periods.

Ported from za_local.patches.v1_1.backfill_emp201_submission_keys as part
of absorbing za_local into ir - EMP201 Submission now lives in ir_payroll.
"""

import hashlib

import frappe
from frappe import _


def execute():
	if not frappe.db.table_exists("EMP201 Submission"):
		return

	rows = frappe.get_all(
		"EMP201 Submission",
		fields=["name", "company", "fiscal_year", "month", "docstatus"],
		order_by="creation asc",
	)
	active_keys = {}
	for row in rows:
		if not (row.company and row.fiscal_year and row.month):
			continue
		identity = "|".join((row.company, row.fiscal_year, row.month))
		base_key = hashlib.sha256(identity.encode()).hexdigest()
		if row.docstatus != 2:
			if existing := active_keys.get(base_key):
				frappe.throw(
					_(
						"EMP201 Submissions {0} and {1} are both active for the same company and period. "
						"Cancel or delete the duplicate before migrating."
					).format(existing, row.name),
					title=_("Duplicate EMP201 Period"),
				)
			active_keys[base_key] = row.name
			key = base_key
		else:
			key = hashlib.sha256(f"{base_key}|cancelled|{row.name}".encode()).hexdigest()

		frappe.db.set_value(
			"EMP201 Submission",
			row.name,
			"submission_key",
			key,
			update_modified=False,
		)
