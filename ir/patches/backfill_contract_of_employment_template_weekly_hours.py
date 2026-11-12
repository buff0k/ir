# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Contract of Employment gained a third Working Hours Type - "Weekly Hours
of Work" (a target number of hours per week, with no fixed days/times at
all - unlike Fixed Hours or Shift Worker) - alongside its own new
weekly_hours_of_work field and the shift:weekly condition/weekly_hours
variable in the Template engine (_legacy_working_hours() in
contract_of_employment_template.py). That function only ever affects a
Template's wording at generation time (import_legacy_contract_types(), which
can only ever update a Draft - see its own docstring): the 9 real Templates
already submitted before this change still carry the old Working Hours
wording, with no shift:weekly clause in it at all. A Contract of Employment
set to Weekly Hours of Work would still render correctly once the Template
is regenerated (the clause itself is conditional, so it was simply never
reached before) - this patch is what makes that happen for the 9 that
already exist.

Same pattern as every other Template-wording correction this migration has
made: regenerates contract_markdown/contract_wording for every submitted
Template that was itself imported from a still-existing Contract Type
(contract_name match) and writes it directly via frappe.db.set_value(),
bypassing the submit lock - safe without an amend/cancel cycle because a
Template's contract_wording is only ever read live, at render time, by a
Contract of Employment still in Draft; an already-submitted CoE's
generated_contract is frozen forever regardless of what its Template says
afterwards. As its final step, also re-renders every currently open Draft
Contract of Employment via Document.save() - Document.submit() sets
docstatus=1 *before* calling save(), so a Draft that went straight to
Submit with no intervening Save would otherwise freeze stale wording
forever (see backfill_contract_of_employment_template_deduction_numbering.py
for the fuller explanation - this patch is deliberately kept separate
rather than folded into that one, since by the time *that* patch first
actually runs on a site that's never run it before - e.g. prod, after its
earlier failed attempt - it already regenerates wording from this turn's
fully-current _legacy_contract_markdown(), making this patch a same-site
no-op there; it only has real work to do on a site - e.g. this lab - where
that earlier patch already ran under older code).

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
		"backfill_contract_of_employment_template_weekly_hours: "
		f"{updated} submitted Template(s) re-rendered with the Weekly Hours of Work clause, "
		f"{len(skipped_no_contract_type)} skipped (no matching Contract Type): {skipped_no_contract_type}, "
		f"{drafts_rerendered} open Draft(s) re-rendered, {len(drafts_skipped)} Draft(s) skipped "
		f"(already invalid before this patch): {drafts_skipped}"
	)
