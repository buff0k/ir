# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

from ir.industrial_relations.doctype.written_outcome.written_outcome import (
	_excel_style_letters,
)


def execute():
	"""Written Outcome now auto-generates evidence_annexure ("Annexure A",
	"Annexure B", ...) as a single continuous sequence across
	complainant_evidence then accused_evidence, so that "[Annexure X]" typed
	into a summary field unambiguously resolves to one evidence row at print
	time. Existing evidence rows predate this and have blank/free-text
	values, so backfill them here rather than waiting on each record's next
	manual save. Scoped strictly to parenttype = "Written Outcome" - the
	same "Attach Evidence" child doctype is also used by Anonymous Report,
	whose rows must not be touched.
	"""
	if not frappe.db.exists("DocType", "Written Outcome"):
		return

	if not frappe.db.exists("DocType", "Attach Evidence"):
		return

	for name in frappe.get_all("Written Outcome", pluck="name"):
		complainant_rows = frappe.get_all(
			"Attach Evidence",
			filters={
				"parent": name,
				"parenttype": "Written Outcome",
				"parentfield": "complainant_evidence",
			},
			fields=["name"],
			order_by="idx asc",
		)
		accused_rows = frappe.get_all(
			"Attach Evidence",
			filters={
				"parent": name,
				"parenttype": "Written Outcome",
				"parentfield": "accused_evidence",
			},
			fields=["name"],
			order_by="idx asc",
		)

		for i, row in enumerate(complainant_rows + accused_rows):
			frappe.db.set_value(
				"Attach Evidence",
				row.name,
				"evidence_annexure",
				f"Annexure {_excel_style_letters(i)}",
				update_modified=False,
			)

	frappe.db.commit()
