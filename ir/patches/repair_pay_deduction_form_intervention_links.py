"""Repair Pay Deduction links skipped by the original migration patch.

The first issued migration called ``table_exists`` with an already-prefixed
``tabPay Deduction Form`` value. Frappe prefixes the supplied DocType itself,
so that check looked for ``tabtabPay Deduction Form`` and returned early.
This separately named, idempotent patch ensures sites where the first patch is
already recorded in Patch Log still receive the data migration.
"""

import frappe


DOCTYPE = "Pay Deduction Form"

LEGACY_SOURCES = (
    (
        "linked_disciplinary_action",
        "linked_disciplinary_action_processed",
        "Disciplinary Action",
    ),
    (
        "linked_poor_performance",
        "linked_poor_performance_processed",
        "Poor Performance",
    ),
)


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return

    required_columns = (
        "ir_intervention",
        "linked_intervention",
        "linked_intervention_processed",
    )
    if not all(frappe.db.has_column(DOCTYPE, field) for field in required_columns):
        return

    table = f"`tab{DOCTYPE}`"

    for source_field, processed_field, source_doctype in LEGACY_SOURCES:
        if not frappe.db.has_column(DOCTYPE, source_field):
            continue

        processed_expression = "0"
        if frappe.db.has_column(DOCTYPE, processed_field):
            processed_expression = f"COALESCE(`{processed_field}`, 0)"

        frappe.db.sql(
            f"""
            UPDATE {table}
               SET `ir_intervention` = %s,
                   `linked_intervention` = `{source_field}`,
                   `linked_intervention_processed` = {processed_expression}
             WHERE COALESCE(`{source_field}`, '') != ''
               AND (
                    COALESCE(`ir_intervention`, '') = ''
                    OR COALESCE(`linked_intervention`, '') = ''
               )
            """,
            (source_doctype,),
        )
