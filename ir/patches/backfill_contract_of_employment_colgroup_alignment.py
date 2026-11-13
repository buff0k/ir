# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""render_contract() merges each heading with whatever row immediately
follows it into one atomic <tr> (a small nested table), so wkhtmltopdf
never orphans a heading at the bottom of a page. That made the *outer*
table's very first row a colspan=2 cell - every contract opens on its
first heading, which is always merged with its first clause - and under
table-layout:fixed, a colspan cell in a table's first row breaks the
column-width detection that an explicit width:70px on every <td> was
meant to guarantee (confirmed against a real generated PDF: every
heading+first-row pair sat flush left while every other row was pushed
right, throughout the whole document). Fixed by giving both the outer
table and every nested merge-block table an explicit <colgroup>, which
pins column widths outright regardless of what any row contains.

Like every other render_contract() fix this migration has made,
this only affects wording generated from here on - a Contract of
Employment's generated_contract is rendered once, in validate(), and
frozen from then on (see backfill_contract_of_employment_template_
weekly_hours.py for the fuller explanation). This patch's only job is
re-rendering every currently open Draft CoE through the fixed engine via
Document.save(), so the alignment fix actually reaches documents that
already exist. Already-submitted/cancelled CoEs keep their original,
frozen wording - never regenerated, per standing policy.

Idempotent: re-saving a Draft whose wording is already colgroup-fixed is
harmless (it just re-renders to the same output).
"""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.table_exists("Contract of Employment"):
		return

	rerendered = 0
	skipped = []
	for name in frappe.get_all("Contract of Employment", filters={"docstatus": 0}, pluck="name"):
		doc = frappe.get_doc("Contract of Employment", name)
		try:
			doc.save(ignore_permissions=True)
			rerendered += 1
		except frappe.ValidationError as e:
			skipped.append((name, str(e)))

	frappe.db.commit()
	frappe.logger().info(
		"backfill_contract_of_employment_colgroup_alignment: "
		f"{rerendered} open Draft Contract of Employment(s) re-rendered with the colgroup alignment fix, "
		f"{len(skipped)} skipped (already invalid before this patch): {skipped}"
	)
