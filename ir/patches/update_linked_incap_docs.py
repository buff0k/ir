# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

PARENT_DOCTYPE = "Incapacity Proceedings"

LINKED_TABLES = {
    "linked_nta": ("NTA Hearing", "linked_nta", "linked_incapacity_proceeding"),
    "linked_outcome": ("Disciplinary Outcome Report", "linked_outcome", "linked_incapacity_proceeding"),
    "linked_dismissal": ("Dismissal Form", "linked_dismissal", "linked_incapacity_proceeding"),
    "linked_demotion": ("Demotion Form", "linked_demotion", "linked_incapacity_proceeding"),
    "linked_pay_reduction": ("Pay Reduction Form", "linked_pay_reduction", "linked_incapacity_proceeding"),
    "linked_not_guilty": ("Not Guilty Form", "linked_not_guilty", "linked_incapacity_proceeding"),
    "linked_suspension": ("Suspension Form", "linked_suspension", "linked_incapacity_proceeding"),
    "linked_vsp": ("Voluntary Seperation Agreement", "linked_vsp", "linked_incapacity_proceeding"),
    "linked_cancellation": ("Hearing Cancellation Form", "linked_cancellation", "linked_incapacity_proceeding"),
}


def execute():
    frappe.flags.ignore_permissions = True

    if not frappe.db.exists("DocType", PARENT_DOCTYPE):
        return

    active_mappings = _get_active_mappings()
    if not active_mappings:
        return

    for row in frappe.get_all(PARENT_DOCTYPE, fields=["name"]):
        parent = frappe.get_doc(PARENT_DOCTYPE, row.name)
        parent.flags.ignore_validate_update_after_submit = True

        for parent_field, mapping in active_mappings.items():
            target_doctype, child_table_field, back_reference = mapping
            parent.set(parent_field, [])

            linked_documents = frappe.get_all(
                target_doctype,
                filters={back_reference: parent.name},
                fields=["name"],
                order_by="creation asc, name asc",
            )

            for linked_document in linked_documents:
                parent.append(
                    parent_field,
                    {child_table_field: linked_document.name},
                )

        parent.save(ignore_permissions=True)


def _get_active_mappings():
    parent_meta = frappe.get_meta(PARENT_DOCTYPE)
    active = {}

    for parent_field, mapping in LINKED_TABLES.items():
        target_doctype, child_table_field, back_reference = mapping
        parent_df = parent_meta.get_field(parent_field)

        if not parent_df or parent_df.fieldtype not in ("Table", "Table MultiSelect"):
            continue

        if not frappe.db.exists("DocType", target_doctype):
            continue

        if not frappe.db.has_column(target_doctype, back_reference):
            continue

        child_doctype = parent_df.options
        if not child_doctype or not frappe.db.exists("DocType", child_doctype):
            continue

        if not frappe.db.has_column(child_doctype, child_table_field):
            continue

        active[parent_field] = mapping

    return active
