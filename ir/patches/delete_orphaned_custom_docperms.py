# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Delete Custom DocPerm rows whose parent DocType no longer exists.

Deleted IR forms (Hearing Cancellation Form, Not Guilty Form, NTA Hearing,
Disciplinary Outcome Report, Occupational Level) and the removed lending
doctypes (Loan Repayment, Loan Type, ...) left their Custom DocPerm rows
behind. Frappe 16.35's File permission query calls frappe.get_meta() on
every doctype the user can read, so each orphan raises DoesNotExistError
("DocType <X> not found") on any File query by a non-Administrator user -
which surfaces as a failed save after attaching a file on any form.
"""

import frappe


def execute():
    orphans = frappe.db.sql_list(
        """
        SELECT DISTINCT cdp.parent
        FROM `tabCustom DocPerm` cdp
        WHERE NOT EXISTS (SELECT 1 FROM `tabDocType` dt WHERE dt.name = cdp.parent)
        """
    )
    if not orphans:
        return

    frappe.db.delete("Custom DocPerm", {"parent": ("in", orphans)})
    frappe.clear_cache()
