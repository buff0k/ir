# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

DOCTYPE = "Site Organogram"


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    if not frappe.db.has_column("Site Organogram Mappings", "spare_swing"):
        return

    for row in frappe.get_all(DOCTYPE, fields=["name", "docstatus"]):
        if row.docstatus == 2:
            continue

        doc = frappe.get_doc(DOCTYPE, row.name)
        doc.flags.ignore_validate_update_after_submit = True
        doc.flags.ignore_permissions = True
        # Older Site Organogram records predate site_plan/effective_from/
        # shift_design becoming mandatory - this patch only needs to re-run
        # normalize_mappings() (via save()) to fix up spare_swing, not
        # enforce fields that didn't exist when these records were created.
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)

    frappe.db.commit()
