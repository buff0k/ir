# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

DOCTYPE = "Suspension Form"
TABLE = "tabSuspension Form"

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

    required_new_columns = {
        "ir_intervention",
        "linked_intervention",
        "linked_intervention_processed",
        "suspension_nature",
        "remuneration_status",
    }
    if not required_new_columns.issubset(_columns()):
        frappe.throw(
            "Suspension Form refactor patch must run after the new DocType model has synced."
        )

    _migrate_source_links()
    _migrate_suspension_classification()
    _remove_precautionary_outcomes_from_sources()


def _columns():
    return {
        row.Field
        for row in frappe.db.sql(f"SHOW COLUMNS FROM `{TABLE}`", as_dict=True)
    }


def _migrate_source_links():
    columns = _columns()

    for link_field, processed_field, source_doctype in LEGACY_LINKS:
        if link_field not in columns:
            continue

        processed_expression = (
            f"COALESCE(`{processed_field}`, 0)"
            if processed_field in columns
            else "0"
        )

        frappe.db.sql(
            f"""
            UPDATE `{TABLE}`
            SET
                `ir_intervention` = %s,
                `linked_intervention` = `{link_field}`,
                `linked_intervention_processed` = GREATEST(
                    COALESCE(`linked_intervention_processed`, 0),
                    {processed_expression}
                )
            WHERE
                COALESCE(`linked_intervention`, '') = ''
                AND COALESCE(`{link_field}`, '') != ''
            """,
            source_doctype,
        )


def _migrate_suspension_classification():
    columns = _columns()
    if "suspension_type" not in columns:
        return

    # Historical usage was explicit:
    # Paid Suspension   -> Precautionary, Paid
    # Unpaid Suspension -> Punitive, Unpaid
    # Compare both the Offence Outcome name and its display value.
    frappe.db.sql(
        f"""
        UPDATE `{TABLE}` sf
        LEFT JOIN `tabOffence Outcome` oo
            ON oo.name = sf.suspension_type
        SET
            sf.suspension_nature = CASE
                WHEN LOWER(TRIM(COALESCE(oo.disc_offence_out, sf.suspension_type, '')))
                    = 'paid suspension'
                    THEN 'Precautionary'
                WHEN LOWER(TRIM(COALESCE(oo.disc_offence_out, sf.suspension_type, '')))
                    = 'unpaid suspension'
                    THEN 'Punitive'
                ELSE 'Punitive'
            END,
            sf.remuneration_status = CASE
                WHEN LOWER(TRIM(COALESCE(oo.disc_offence_out, sf.suspension_type, '')))
                    = 'paid suspension'
                    THEN 'Paid'
                WHEN LOWER(TRIM(COALESCE(oo.disc_offence_out, sf.suspension_type, '')))
                    = 'unpaid suspension'
                    THEN 'Unpaid'
                ELSE 'Unpaid'
            END
        WHERE
            COALESCE(sf.suspension_nature, '') = ''
            OR COALESCE(sf.remuneration_status, '') = ''
        """
    )

    # A precautionary suspension is not an outcome. Clear the old outcome link
    # only after its meaning has been captured in the new fields.
    frappe.db.sql(
        f"""
        UPDATE `{TABLE}`
        SET `suspension_type` = NULL
        WHERE `suspension_nature` = 'Precautionary'
        """
    )


def _remove_precautionary_outcomes_from_sources():
    # Correct historical source records only when the source still carries the
    # exact legacy Paid Suspension outcome and the same outcome date. This guard
    # avoids removing a later, unrelated final outcome.
    rows = frappe.db.sql(
        f"""
        SELECT
            sf.name,
            sf.ir_intervention,
            sf.linked_intervention,
            sf.outcome_date,
            sf.modified,
            oo.name AS paid_outcome_name
        FROM `{TABLE}` sf
        LEFT JOIN `tabOffence Outcome` oo
            ON LOWER(TRIM(oo.disc_offence_out)) = 'paid suspension'
        WHERE
            sf.suspension_nature = 'Precautionary'
            AND COALESCE(sf.ir_intervention, '') != ''
            AND COALESCE(sf.linked_intervention, '') != ''
        """,
        as_dict=True,
    )

    for row in rows:
        if row.ir_intervention not in {
            "Disciplinary Action",
            "Incapacity Proceedings",
            "Poor Performance",
        }:
            continue

        if not frappe.db.exists(row.ir_intervention, row.linked_intervention):
            continue

        source = frappe.get_doc(row.ir_intervention, row.linked_intervention)
        current_outcome = source.get("outcome")
        current_date = source.get("outcome_date")

        if not current_outcome:
            continue

        outcome_label = frappe.db.get_value(
            "Offence Outcome",
            current_outcome,
            "disc_offence_out",
        ) or current_outcome

        if (outcome_label or "").strip().lower() != "paid suspension":
            continue

        if row.outcome_date and current_date and str(row.outcome_date) != str(current_date):
            continue

        updates = {}
        for fieldname in ("outcome", "outcome_date", "outcome_start", "outcome_end"):
            if source.meta.has_field(fieldname):
                updates[fieldname] = None

        if updates:
            frappe.db.set_value(
                row.ir_intervention,
                row.linked_intervention,
                updates,
                update_modified=False,
            )
