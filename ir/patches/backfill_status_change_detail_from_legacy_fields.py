# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Backfills Status Change Detail rows for every existing Status Change
Form, derived from its legacy current_*/new_* fields (Designation, Branch,
Conditions of Employment, Hourly/Basic Rate, and the six simple allowance
fields) - see status_change_detail_backfill.build_status_change_detail_rows
for the row-building rules (skips anything that didn't actually change,
including null/blank pairs for fields that predate a given record).

Registered in patches.txt ([post_model_sync], after
fix_status_change_form_migrated_creation_dates) - runs automatically as part
of a normal `bench migrate`. Verified on dev first via a manual
`bench execute ir.patches.backfill_status_change_detail_from_legacy_fields.execute`
run against all 386 real records before being wired in.

Runs over every Status Change Form regardless of docstatus (Draft,
Submitted, and Cancelled alike) - this only mirrors data the record
already carries into its own new child table, it never re-derives or
changes any business outcome, so docstatus is irrelevant here. Written as
a single raw bulk_insert - never Document.insert()/.save() - so it never
touches Status Change Form's own hooks (notifications, validate,
on_submit) for records that are, in every case here, already fully
processed. Idempotent: skips any form that already has Status Change
Detail rows, so re-running is always safe.

Reads the legacy current_*/new_* columns via raw SQL, not
frappe.db.get_all()/get_doc() - deliberately, because this patch is meant
to still work once those fields are removed from Status Change Form's own
DocType JSON. Frappe's schema sync (frappe/database/schema.py, DBTable.sync)
only ever adds/alters columns for fields that still exist in a doctype's
JSON - it has no code path that drops a column for a field that's been
removed, so the underlying tabStatus Change Form columns and their data
survive a field removal untouched. But ORM-level field-aware reads
(get_all/get_doc) go through the doctype's meta, which no longer knows
about a removed field - so this patch bypasses that layer entirely and
reads the physical columns directly, exactly as frappe.db.sql always can.
"""

import frappe

from ir.industrial_relations.doctype.status_change_form.status_change_detail_backfill import (
    build_status_change_detail_rows,
)

SOURCE_FIELDS = [
    "name",
    "current_designation",
    "new_designation",
    "current_branch",
    "new_branch",
    "current_conditions",
    "new_conditions",
    "current_rate",
    "new_rate",
    "current_travel",
    "new_travel",
    "current_housing",
    "new_housing",
    "current_safety",
    "new_safety",
    "current_shift",
    "new_shift",
    "current_phone",
    "new_phone",
    "current_opencast",
    "new_opencast",
]

DETAIL_COLUMNS = [
    "name",
    "parent",
    "parenttype",
    "parentfield",
    "idx",
    "docstatus",
    "owner",
    "modified_by",
    "creation",
    "modified",
    "change_type",
    "old_value",
    "new_value",
    "old_condition",
    "new_condition",
    "salary_component",
    "old_amount",
    "new_amount",
]


def execute():
    if not frappe.db.table_exists("Status Change Form") or not frappe.db.table_exists("Status Change Detail"):
        return

    already_backfilled = {
        row[0]
        for row in frappe.db.sql(
            "SELECT DISTINCT parent FROM `tabStatus Change Detail` WHERE parenttype = 'Status Change Form'"
        )
    }

    columns = ", ".join(f"`{f}`" for f in SOURCE_FIELDS)
    forms = frappe.db.sql(f"SELECT {columns} FROM `tabStatus Change Form`", as_dict=True)

    now = frappe.utils.now()
    values = []
    for form in forms:
        if form.name in already_backfilled:
            continue

        for idx, detail in enumerate(build_status_change_detail_rows(form), start=1):
            values.append(
                (
                    frappe.generate_hash(length=10),
                    form.name,
                    "Status Change Form",
                    "status_change_details",
                    idx,
                    0,
                    "Administrator",
                    "Administrator",
                    now,
                    now,
                    detail.get("change_type"),
                    detail.get("old_value"),
                    detail.get("new_value"),
                    detail.get("old_condition"),
                    detail.get("new_condition"),
                    detail.get("salary_component"),
                    detail.get("old_amount") or 0,
                    detail.get("new_amount") or 0,
                )
            )

    if not values:
        return

    frappe.db.bulk_insert("Status Change Detail", fields=DETAIL_COLUMNS, values=values)
    frappe.db.commit()
