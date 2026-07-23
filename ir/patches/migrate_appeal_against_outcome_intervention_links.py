# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


DOCTYPE = "Appeal Against Outcome"

LEGACY_LINKS = (
    (
        "linked_disciplinary_action",
        "linked_disciplinary_action_processed",
        "Disciplinary Action",
    ),
    (
        "linked_incapacity_proceeding",
        "linked_incapacity_proceeding_processed",
        "Incapacity Proceedings",
    ),
    (
        "linked_poor_performance",
        "linked_poor_performance_processed",
        "Poor Performance",
    ),
)


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    if not _has_columns(
        "ir_intervention",
        "linked_intervention",
        "linked_intervention_processed",
    ):
        return

    for source_field, processed_field, intervention in LEGACY_LINKS:
        if not frappe.db.has_column(DOCTYPE, source_field):
            continue

        processed_expression = "0"
        if frappe.db.has_column(DOCTYPE, processed_field):
            processed_expression = f"COALESCE(`{processed_field}`, 0)"

        frappe.db.sql(
            f"""
            UPDATE `tabAppeal Against Outcome`
            SET
                `ir_intervention` = %(intervention)s,
                `linked_intervention` = `{source_field}`,
                `linked_intervention_processed` = {processed_expression}
            WHERE
                (`linked_intervention` IS NULL
                 OR `linked_intervention` = '')
                AND `{source_field}` IS NOT NULL
                AND `{source_field}` != ''
            """,
            {"intervention": intervention},
        )


def _has_columns(*fieldnames):
    return all(
        frappe.db.has_column(DOCTYPE, fieldname)
        for fieldname in fieldnames
    )
