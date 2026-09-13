# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Shared helper for patches that migrate data OUT of an old renamed/retired
doctype. Not a patch itself - never list this file in patches.txt.

Some of these patches were only ever meant to run on a site that upgraded
through the version where the old doctype's Python files still existed in
the app - that's when the patch actually does its job and the data still
gets migrated correctly. A site whose database was instead restored from a
backup taken *before* the rename and updated straight to the current app
code skips past that window entirely: the old doctype's folder has already
been deleted from the app's source as part of the normal post-migration
cleanup, so there is no supported way for the patch to still process it
(frappe.get_doc(OLD_DOCTYPE, ...) needs the controller module to be
importable, with no fallback). Rather than trying to reconstruct that data
via raw SQL, the patch should simply recognise "this app no longer even
ships this doctype" and succeed as a no-op - the same way it already does
when the site never had the doctype's *data* in the first place.
"""

from __future__ import annotations

import frappe


def old_doctype_module_exists(doctype: str, module_folder: str = "industrial_relations") -> bool:
    """True iff the ir app's current source still ships doctype's own folder
    (i.e. `frappe.get_doc(doctype, ...)` would actually work). A plain
    filesystem check, deliberately independent of tabDocType/tabDocField -
    those can already be stripped by remove_orphan_doctypes() in the very
    same sync_all() pass that runs right before a post_model_sync patch,
    for a doctype whose data (and even its DocType meta) can still very
    much exist in the database.
    """
    import os

    path = frappe.get_app_path("ir", module_folder, "doctype", frappe.scrub(doctype))
    return os.path.isdir(path)
