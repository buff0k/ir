# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

HISTORY_DOCTYPE = "Disciplinary History"
OUTCOME_DOCTYPE = "Offence Outcome"


def execute():
    if not _schema_exists():
        return

    frappe.db.sql(
        """
        UPDATE `tabDisciplinary History` AS history
        INNER JOIN `tabOffence Outcome` AS outcome
            ON history.sanction = outcome.name
        SET history.sanction = outcome.disc_offence_out
        WHERE history.sanction IS NOT NULL
          AND history.sanction != ''
          AND outcome.disc_offence_out IS NOT NULL
          AND outcome.disc_offence_out != ''
        """
    )


def _schema_exists():
    for doctype in (HISTORY_DOCTYPE, OUTCOME_DOCTYPE):
        if not frappe.db.exists("DocType", doctype):
            return False

    return (
        frappe.db.has_column(HISTORY_DOCTYPE, "sanction")
        and frappe.db.has_column(OUTCOME_DOCTYPE, "disc_offence_out")
    )
