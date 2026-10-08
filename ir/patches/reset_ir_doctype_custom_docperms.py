"""One-time cleanup: delete every Custom DocPerm row for a doctype this app
owns (module == "Industrial Relations"), on every site - prod included.

These rows had drifted from this app's own DocType JSON permissions (in both
directions: some grants broader than the source, some narrower - e.g.
Disciplinary Action's IR User row had collapsed to read=0/write=0/create=0
live, while the shipped JSON grants full access), and Custom DocPerm always
takes precedence over the DocType's own "permissions" array once it exists
for a role - so the live site was never actually running what this app's own
source said it should. The doctype JSON files have now been corrected to
match (with one deliberate exception: IR Manager always keeps Delete, IR
Officer/IR User never get it, regardless of what the stale Custom DocPerm
said), so the Custom DocPerm rows are now pure liability - they'd keep
shadowing the correct, git-tracked permissions on every site that already
has them, including ones this fixture's own filtered scope never covered
(the same way File's "All" row turned out to be a completely untracked,
ad-hoc edit nobody's fixture captured).

Runs pre-model-sync, before fixture import would otherwise try to recreate
the (now intentionally removed) entries in ir/fixtures/custom_docperm.json.
Standard one-time patch - Frappe's Patch Log ensures this never runs twice
on the same site.
"""

import frappe


def execute():
    ir_doctypes = frappe.get_all("DocType", filters={"module": "Industrial Relations"}, pluck="name")
    if not ir_doctypes:
        return

    frappe.db.delete("Custom DocPerm", {"parent": ["in", ir_doctypes]})
    frappe.clear_cache()
