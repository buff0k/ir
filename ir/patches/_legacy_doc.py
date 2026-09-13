# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Shared helper for patches that migrate data OUT of an old renamed/retired
doctype. Not a patch itself - never list this file in patches.txt.

Why this exists: frappe.get_doc(OLD_DOCTYPE, name) requires the doctype's own
Python controller module to still exist on disk (get_controller() ->
import_controller() -> load_doctype_module() does a real `import`, and raises
ImportError/ModuleNotFoundError if the module is missing - there is no
fallback to a generic Document class the way there is for a doctype with no
custom controller file at all). A site whose database was restored from a
backup taken *before* one of these renames happened, then updated straight to
the current app code, still has the old DocType's meta rows and physical
table in the DB (so `frappe.db.exists("DocType", OLD_DOCTYPE)` and
`frappe.get_all(OLD_DOCTYPE, ...)` both work fine) - but the old doctype's own
folder was deleted from the app's source long ago as part of the normal
post-migration cleanup on sites that already ran this patch, so `get_doc()`
crashes the whole `bench migrate` for every site that hasn't run it yet under
current code, even though the data these patches exist to migrate is sitting
right there.

get_legacy_doc() reads the same data via raw SQL instead - frappe.get_meta()
and frappe.db.get_value()/get_all() are purely metadata/table driven and never
import a controller module, so this works whether or not the old doctype's
Python files still exist. The returned frappe._dict supports the exact same
`.get(fieldname)` / attribute access / `.name` / `.docstatus` calling
convention a real Document does for every read-only access pattern these
patches use (they never call a custom controller method on the old doc), so
it's a drop-in replacement for `frappe.get_doc(OLD_DOCTYPE, name)` in that
role only.
"""

from __future__ import annotations

import frappe


def get_legacy_doc(doctype: str, name: str) -> frappe._dict | None:
    """Read `doctype`/`name` as a plain frappe._dict, including its child
    tables, without needing `doctype`'s own controller module to be
    importable. Returns None if the row no longer exists.

    Also carries `.meta` on both the returned doc and every child row (a
    frappe._dict exposes any key as an attribute, so `doc["meta"] = ...` is
    enough to make `old.meta.get_field(...)` work exactly like it would on a
    real Document) - a couple of these patches check `old.meta.get_field(x)`
    / `old_row.meta.get_field(x)` before copying a field across, not just
    `.get(x)`.
    """
    row = frappe.db.get_value(doctype, name, "*", as_dict=True)
    if not row:
        return None

    meta = frappe.get_meta(doctype)
    doc = frappe._dict(row)
    doc["doctype"] = doctype
    doc["name"] = name
    doc["meta"] = meta

    for table_field in meta.get_table_fields():
        child_meta = frappe.get_meta(table_field.options)
        child_rows = frappe.get_all(
            table_field.options,
            filters={"parent": name, "parenttype": doctype, "parentfield": table_field.fieldname},
            fields="*",
            order_by="idx asc",
        )
        wrapped_rows = []
        for child_row in child_rows:
            wrapped = frappe._dict(child_row)
            wrapped["meta"] = child_meta
            wrapped_rows.append(wrapped)
        doc[table_field.fieldname] = wrapped_rows

    return doc
