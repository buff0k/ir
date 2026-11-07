# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Corrects `creation`/`owner` on Status Change Form records produced by
migrate_site_transfer_form_to_status_change_form. That patch pre-set
doc.creation/doc.owner from the source Site Transfer Form row before
doc.insert(), relying on frappe.flags.in_patch (set during normal patch
execution) to stop Document.set_user_and_timestamp() from overwriting them.
On at least one bench that flag wasn't set the way it was when this was
verified, so every migrated record's creation/owner silently defaulted to
"now"/whoever ran the migrate instead of the original historical value.

Deliberately a raw SQL UPDATE, never frappe.get_doc(...).insert()/.save() -
going through Document lifecycle again would refire after_insert
notifications for records that were already (wrongly) notified about once
by the original patch. Idempotent: the WHERE clause only touches rows that
still differ from their source.
"""

import frappe

SOURCE_DOCTYPE = "Site Transfer Form"
TARGET_DOCTYPE = "Status Change Form"


def execute():
    if not frappe.db.table_exists(SOURCE_DOCTYPE) or not frappe.db.table_exists(TARGET_DOCTYPE):
        return

    frappe.db.sql(
        f"""
        UPDATE `tab{TARGET_DOCTYPE}` target
        INNER JOIN `tab{SOURCE_DOCTYPE}` source ON source.name = target.name
        SET target.creation = source.creation,
            target.owner = source.owner
        WHERE target.creation != source.creation
           OR target.owner != source.owner
        """
    )
    frappe.db.commit()
