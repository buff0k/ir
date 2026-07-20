import frappe


LEGACY_SOURCES = (
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
    if not frappe.db.table_exists("Pay Reduction Form"):
        return

    columns = set(frappe.db.get_table_columns("Pay Reduction Form"))
    if not {"ir_intervention", "linked_intervention"}.issubset(columns):
        return

    legacy_fields = [
        fieldname
        for source_field, processed_field, _doctype in LEGACY_SOURCES
        for fieldname in (source_field, processed_field)
        if fieldname in columns
    ]

    fields = [
        "name",
        "ir_intervention",
        "linked_intervention",
        "linked_intervention_processed",
        *legacy_fields,
    ]

    for row in frappe.get_all("Pay Reduction Form", fields=fields):
        if row.linked_intervention and row.ir_intervention:
            continue

        source_doctype = None
        source_name = None
        processed = 0

        for source_field, processed_field, doctype in LEGACY_SOURCES:
            if source_field not in columns:
                continue

            candidate = row.get(source_field)
            if not candidate:
                continue

            source_doctype = doctype
            source_name = candidate
            if processed_field in columns:
                processed = int(bool(row.get(processed_field)))
            break

        if not source_name:
            continue

        frappe.db.set_value(
            "Pay Reduction Form",
            row.name,
            {
                "ir_intervention": source_doctype,
                "linked_intervention": source_name,
                "linked_intervention_processed": processed,
            },
            update_modified=False,
        )
