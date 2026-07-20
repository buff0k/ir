# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

DOCTYPE = "Demotion Form"


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return

    columns = set(frappe.db.get_table_columns(DOCTYPE))
    required_new = {"ir_intervention", "linked_intervention", "linked_intervention_processed"}
    if not required_new.issubset(columns):
        return

    mappings = [
        ("linked_disciplinary_action", "linked_disciplinary_action_processed", "Disciplinary Action"),
        ("linked_incapacity_proceeding", "linked_incapacity_proceeding_processed", "Incapacity Proceedings"),
        ("linked_poor_performance", "linked_poor_performance_processed", "Poor Performance"),
    ]

    fields = ["name", "docstatus", "position", "new_position", "to_date", "ir_intervention", "linked_intervention"]
    for link_field, processed_field, _doctype in mappings:
        if link_field in columns:
            fields.append(link_field)
        if processed_field in columns:
            fields.append(processed_field)

    for row in frappe.get_all(DOCTYPE, fields=list(dict.fromkeys(fields))):
        updates = {}
        if not row.ir_intervention or not row.linked_intervention:
            for link_field, processed_field, source_doctype in mappings:
                linked = row.get(link_field) if link_field in columns else None
                if linked:
                    updates["ir_intervention"] = source_doctype
                    updates["linked_intervention"] = linked
                    updates["linked_intervention_processed"] = int(bool(row.get(processed_field))) if processed_field in columns else 1
                    break

        if row.docstatus == 1:
            updates.setdefault("demotion_applied", 1)
            # Do not guess reversal status. The scheduler safely checks the Employee's current designation.
            updates.setdefault("demotion_reversed", 0)

        if updates:
            frappe.db.set_value(DOCTYPE, row.name, updates, update_modified=False)
