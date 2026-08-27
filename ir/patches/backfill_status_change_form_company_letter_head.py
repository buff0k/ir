# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Status Change Form had no Company/Letter Head fields at all, unlike every
other IR process form tied to an Employee - every existing record (and every
signed print of one) used the site's default Letter Head instead of the
Employee's own Company's. The doctype now carries and auto-populates both
fields going forward (see StatusChangeForm.validate()); this backfills every
existing record from its own Employee, once.
"""

import frappe

DOCTYPE = "Status Change Form"


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return

    columns = set(frappe.db.get_table_columns(DOCTYPE))
    if not {"company", "letter_head", "employee"}.issubset(columns):
        return

    # Filtering "company is blank OR letter_head is blank" at the DB level
    # via frappe.get_all's `in (None, "")` is unreliable (NULL never matches
    # an IN list, the same class of gotcha as an unguarded date "<" filter
    # treating NULL as a real value) - fetch every row with an Employee set
    # and check blankness in Python instead.
    rows = frappe.get_all(
        DOCTYPE,
        filters={"employee": ["is", "set"]},
        fields=["name", "employee", "company", "letter_head"],
    )

    letter_head_by_company = {}

    for row in rows:
        if row.company and row.letter_head:
            continue

        company = frappe.db.get_value("Employee", row.employee, "company")
        if not company:
            continue

        if company not in letter_head_by_company:
            letter_head_by_company[company] = frappe.db.get_value("Company", company, "default_letter_head")
        letter_head = letter_head_by_company[company]

        updates = {}
        if row.company != company:
            updates["company"] = company
        if row.letter_head != letter_head:
            updates["letter_head"] = letter_head

        if updates:
            frappe.db.set_value(DOCTYPE, row.name, updates, update_modified=False)
