# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

WARNING_DOCTYPE = "Warning Form"
OUTCOME_DOCTYPE = "Offence Outcome"


def execute():
    if not _schema_exists():
        return

    target_fields = [
        fieldname
        for fieldname in ("disc_offence_out", "expiry_days")
        if frappe.db.has_column(WARNING_DOCTYPE, fieldname)
        and frappe.db.has_column(OUTCOME_DOCTYPE, fieldname)
    ]

    if not target_fields:
        return

    warning_forms = frappe.get_all(
        WARNING_DOCTYPE,
        fields=["name", "warning_type"],
    )

    for warning_form in warning_forms:
        if not warning_form.warning_type:
            continue

        outcome = frappe.db.get_value(
            OUTCOME_DOCTYPE,
            warning_form.warning_type,
            target_fields,
            as_dict=True,
        )

        if not outcome:
            continue

        frappe.db.set_value(
            WARNING_DOCTYPE,
            warning_form.name,
            {fieldname: outcome.get(fieldname) for fieldname in target_fields},
            update_modified=False,
        )


def _schema_exists():
    for doctype in (WARNING_DOCTYPE, OUTCOME_DOCTYPE):
        if not frappe.db.exists("DocType", doctype):
            return False

    return frappe.db.has_column(WARNING_DOCTYPE, "warning_type")
