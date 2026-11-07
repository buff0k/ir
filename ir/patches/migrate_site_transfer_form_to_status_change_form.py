# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Site Transfer Form is deprecated in favour of Status Change Form's own
current_branch/new_branch fields. Recreates every existing Site Transfer
Form record as a Status Change Form record under the exact same `name`
(name uniqueness is per-table in Frappe, so this is safe and lets File/
Comment references move with a plain column update instead of a rewrite),
then moves their attachments/comments across. Idempotent - re-running skips
any name that already exists on Status Change Form.

docstatus is never pre-set before insert(): for a brand-new document,
check_docstatus_transition() treats docstatus=1 as an implicit submit (would
replay on_submit's Employee-mutation side effects a second time) and raises
outright for docstatus=2. So every record is inserted as a draft and then
flipped via a direct frappe.db.set_value() write, which touches neither
on_submit nor on_cancel.
"""

import frappe

SOURCE_DOCTYPE = "Site Transfer Form"
TARGET_DOCTYPE = "Status Change Form"

SOURCE_FIELDS = [
    "name", "docstatus", "creation", "owner",
    "requested_by", "requested_by_name", "requested_by_designation",
    "employee", "employee_name", "designation",
    "current_branch", "new_branch",
    "transfer_date", "attach", "reason", "company", "letter_head",
]


def execute():
    if not frappe.db.table_exists(SOURCE_DOCTYPE) or not frappe.db.table_exists(TARGET_DOCTYPE):
        return

    rows = frappe.db.get_all(SOURCE_DOCTYPE, fields=SOURCE_FIELDS, order_by="creation asc")

    migrated = 0
    for row in rows:
        if frappe.db.exists(TARGET_DOCTYPE, row.name):
            continue

        doc = frappe.new_doc(TARGET_DOCTYPE)
        doc.flags.ignore_validate = True
        doc.creation = row.creation
        doc.owner = row.owner

        doc.requested_by = row.requested_by
        doc.requested_by_name = row.requested_by_name
        doc.requested_by_designation = row.requested_by_designation
        doc.employee = row.employee
        doc.employee_name = row.employee_name
        # No designation change occurred on a Site Transfer Form - current and
        # new both carry the same snapshot, which also satisfies new_designation's
        # reqd=1 honestly rather than inventing a value.
        doc.current_designation = row.designation
        doc.new_designation = row.designation
        doc.current_branch = row.current_branch
        doc.new_branch = row.new_branch
        doc.effective_date = row.transfer_date
        doc.attach = row.attach
        doc.reason = row.reason
        doc.company = row.company
        doc.letter_head = row.letter_head
        # Remuneration/conditions fields have no Site Transfer Form source data
        # at all - left at their type defaults (0 / blank).

        doc.insert(set_name=row.name, ignore_mandatory=True, ignore_permissions=True)

        if row.docstatus:
            frappe.db.set_value(TARGET_DOCTYPE, row.name, "docstatus", row.docstatus, update_modified=False)

        migrated += 1

    _move_shared_artifacts()

    frappe.db.commit()
    frappe.logger().info(
        f"migrate_site_transfer_form_to_status_change_form: migrated {migrated} of {len(rows)} record(s)."
    )


def _move_shared_artifacts():
    """Repoints File/Comment/Version/Communication/DocShare rows from Site
    Transfer Form to Status Change Form - safe in bulk since every migrated
    name now exists identically in both tables, so no name needs to change."""
    if frappe.db.table_exists("File"):
        frappe.db.sql(
            "UPDATE `tabFile` SET attached_to_doctype = %s WHERE attached_to_doctype = %s",
            (TARGET_DOCTYPE, SOURCE_DOCTYPE),
        )
    if frappe.db.table_exists("Comment"):
        frappe.db.sql(
            "UPDATE `tabComment` SET reference_doctype = %s WHERE reference_doctype = %s",
            (TARGET_DOCTYPE, SOURCE_DOCTYPE),
        )
    if frappe.db.table_exists("Version"):
        frappe.db.sql(
            "UPDATE `tabVersion` SET ref_doctype = %s WHERE ref_doctype = %s",
            (TARGET_DOCTYPE, SOURCE_DOCTYPE),
        )
    if frappe.db.table_exists("Communication"):
        frappe.db.sql(
            "UPDATE `tabCommunication` SET reference_doctype = %s WHERE reference_doctype = %s",
            (TARGET_DOCTYPE, SOURCE_DOCTYPE),
        )
    if frappe.db.table_exists("DocShare"):
        frappe.db.sql(
            "UPDATE `tabDocShare` SET share_doctype = %s WHERE share_doctype = %s",
            (TARGET_DOCTYPE, SOURCE_DOCTYPE),
        )
