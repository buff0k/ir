# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Leave Application (core HRMS) already ships its own `letter_head` field,
but nothing in HRMS ever populates it correctly - confirmed some existing
records already have the *System default* Letter Head stamped onto them at
creation time (not blank - a real, wrong value covering the Employee's own
Company's), so this deliberately does NOT skip rows that already have a
letter_head - see ir.overrides.leave_application.set_letter_head_from_company
for the same reasoning on the going-forward fix. Every record's
letter_head is recomputed from its own Company, unconditionally.
"""

import frappe

DOCTYPE = "Leave Application"


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return

    columns = set(frappe.db.get_table_columns(DOCTYPE))
    if not {"company", "letter_head"}.issubset(columns):
        return

    rows = frappe.get_all(
        DOCTYPE,
        filters={"company": ["is", "set"]},
        fields=["name", "company", "letter_head"],
    )

    letter_head_by_company = {}

    for row in rows:
        if row.company not in letter_head_by_company:
            letter_head_by_company[row.company] = frappe.db.get_value(
                "Company", row.company, "default_letter_head"
            )
        letter_head = letter_head_by_company[row.company]

        if letter_head and row.letter_head != letter_head:
            frappe.db.set_value(DOCTYPE, row.name, "letter_head", letter_head, update_modified=False)
