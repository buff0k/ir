# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Remove stale invalid DocType Link rows left over from older installs.

Ported from za_local.sa_setup.install.cleanup_invalid_doctype_links as part
of absorbing za_local into ir - that function ran unconditionally on every
install/migrate even though it is a one-time cleanup, not a recurring task.
"""

import frappe

INVALID_LINKS = (
	("Payroll Entry", "EMP201 Submission", "payroll_entry"),
	("IRP5 Certificate", "EMP501 Reconciliation", "emp501_reconciliation"),
)


def execute():
	if not frappe.db.table_exists("DocType Link"):
		return

	for parent_dt, link_dt, link_field in INVALID_LINKS:
		links_to_delete = frappe.db.sql(
			"""
			SELECT name
			FROM `tabDocType Link`
			WHERE parent = %s
				AND link_doctype = %s
				AND link_fieldname = %s
			""",
			(parent_dt, link_dt, link_field),
			as_dict=1,
		)
		for link in links_to_delete:
			frappe.delete_doc("DocType Link", link.name, force=True, ignore_permissions=True)

	frappe.db.commit()
