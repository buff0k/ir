# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


def execute():
    if not frappe.db.table_exists("Dismissal Form"):
        return

    _migrate_parent_links()
    _migrate_performance_history_parentfield()


def _has_column(fieldname):
    return frappe.db.has_column("Dismissal Form", fieldname)


def _migrate_parent_links():
    required_new = {
        "ir_intervention",
        "linked_intervention",
        "linked_intervention_processed",
    }
    if not all(_has_column(fieldname) for fieldname in required_new):
        return

    legacy_sources = [
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
    ]

    fields = ["name", "ir_intervention", "linked_intervention", "linked_intervention_processed"]
    for source_field, processed_field, _doctype in legacy_sources:
        if _has_column(source_field):
            fields.append(source_field)
        if _has_column(processed_field):
            fields.append(processed_field)

    rows = frappe.get_all("Dismissal Form", fields=list(dict.fromkeys(fields)))

    for row in rows:
        if row.get("ir_intervention") and row.get("linked_intervention"):
            continue

        updates = {}
        for source_field, processed_field, source_doctype in legacy_sources:
            source_name = row.get(source_field)
            if not source_name:
                continue

            updates = {
                "ir_intervention": source_doctype,
                "linked_intervention": source_name,
                "linked_intervention_processed": cint_or_zero(row.get(processed_field)),
            }
            break

        if updates:
            frappe.db.set_value(
                "Dismissal Form",
                row.name,
                updates,
                update_modified=False,
            )


def _migrate_performance_history_parentfield():
    if not frappe.db.table_exists("Performance History"):
        return

    frappe.db.sql(
        """
        UPDATE `tabPerformance History`
           SET parentfield = 'previous_performance_outcomes'
         WHERE parenttype = 'Dismissal Form'
           AND parentfield = 'table_fqxg'
        """
    )


def cint_or_zero(value):
    try:
        return 1 if int(value or 0) else 0
    except (TypeError, ValueError):
        return 0
