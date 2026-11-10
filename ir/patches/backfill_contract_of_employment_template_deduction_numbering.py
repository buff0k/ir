# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Every real Deductions section's wording used the single deductions_table
variable: one ready-made HTML table crammed into a single numbered
sub-paragraph slot, so 2+ deductions on the same contract were never
individually numbered at all (reported after this went live on prod).
_legacy_deductions() (contract_of_employment_template.py) now uses the new
deductions repeat (one deduction_label row per Deduction, each its own
numbered sub-paragraph - e.g. 5.1.1, 5.1.2 - the same mechanism earnings
already uses for Allowances) - but the Templates already submitted before
that fix still carry the old deductions_table wording:
import_legacy_contract_types() can only ever update a Draft (see its own
docstring), so a plain re-run does nothing for them.

Critically, this isn't just a numbering cosmetic issue to leave until the
next convenient resave: contract_of_employment.py's _build_render_context()
no longer populates context.values["deductions_table"] at all (it builds
context.rows["deductions"] instead) - so a Contract of Employment still
rendering against an un-backfilled Template would now show "No deductions
on this contract." regardless of what's actually on it, which is worse
than the bug being fixed. This patch is not optional.

This patch regenerates contract_markdown/contract_wording for every
submitted Template that was itself imported from a still-existing Contract
Type (contract_name match, same convention as everywhere else in this
migration) and writes it directly via frappe.db.set_value(), bypassing the
submit lock - exactly like every other correction this migration has made
to already-submitted documents. Safe without an amend/cancel cycle because
a Template's contract_wording is only ever read live, at render time, by a
Contract of Employment still in Draft; an already-submitted CoE's
generated_contract is frozen forever regardless of what its Template says
afterwards.

As its final step, this patch also re-renders every currently open Draft
Contract of Employment via Document.save() - Document.submit() sets
docstatus=1 *before* calling save() (see frappe.model.document.Document.
_submit()), so validate()'s own "only while still Draft" guard never fires
during a submit itself; a Draft that went straight to Submit with no
intervening Save would otherwise freeze the stale, pre-fix wording forever.
A Draft that's already invalid for an unrelated, pre-existing reason (e.g.
no Earnings row ever captured) is skipped and logged rather than aborting
the whole migration.

Idempotent: skips any Template whose contract_markdown already matches what
_legacy_contract_markdown() would produce today; re-saving a Draft that's
already up to date is harmless.
"""

from __future__ import annotations

import json

import frappe

from ir.industrial_relations.doctype.contract_of_employment_template.contract_of_employment_template import (
	_legacy_contract_markdown,
	parse_markdown,
	to_delta,
)


def execute():
	if not frappe.db.table_exists("Contract of Employment Template"):
		return

	templates = frappe.get_all(
		"Contract of Employment Template",
		filters={"docstatus": 1},
		fields=["name", "contract_name", "contract_markdown"],
	)

	updated = 0
	skipped_no_contract_type = []
	for row in templates:
		if not frappe.db.exists("Contract Type", {"name": row.contract_name, "docstatus": 1}):
			skipped_no_contract_type.append(row.name)
			continue

		markdown, _notes = _legacy_contract_markdown(row.contract_name)
		if markdown == row.contract_markdown:
			continue

		wording = json.dumps(to_delta(parse_markdown(markdown)), ensure_ascii=False)
		frappe.db.set_value(
			"Contract of Employment Template",
			row.name,
			{"contract_markdown": markdown, "contract_wording": wording},
			update_modified=False,
		)
		updated += 1

	drafts_rerendered = 0
	drafts_skipped = []
	for name in frappe.get_all("Contract of Employment", filters={"docstatus": 0}, pluck="name"):
		doc = frappe.get_doc("Contract of Employment", name)
		try:
			doc.save(ignore_permissions=True)
			drafts_rerendered += 1
		except frappe.ValidationError as e:
			drafts_skipped.append((name, str(e)))

	frappe.db.commit()
	frappe.logger().info(
		"backfill_contract_of_employment_template_deduction_numbering: "
		f"{updated} submitted Template(s) re-rendered with numbered Deductions, "
		f"{len(skipped_no_contract_type)} skipped (no matching Contract Type): {skipped_no_contract_type}, "
		f"{drafts_rerendered} open Draft(s) re-rendered, {len(drafts_skipped)} Draft(s) skipped "
		f"(already invalid before this patch): {drafts_skipped}"
	)
