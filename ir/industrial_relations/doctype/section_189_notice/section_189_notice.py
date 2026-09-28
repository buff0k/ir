# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from ir.industrial_relations import utils

STATUTORY_FIELDS = (
	"company",
	"letter_head",
	"reason_for_dismissals",
	"alternatives_considered",
	"selection_method",
	"proposed_implementation_date",
	"implementation_notes",
	"severance_pay_proposal",
	"assistance_offered",
	"future_reemployment",
	"total_initially_affected",
	"total_employees",
	"prior_operational_dismissals_12m",
)


class Section189Notice(Document):
	def autoname(self):
		utils.autoname_by_linked_parent(self, "S189-NOTICE")

	def validate(self):
		if not self.ir_intervention:
			self.ir_intervention = "Retrenchment Process"

	def before_submit(self):
		if not self.recipients:
			frappe.throw(_("Add at least one Recipient before submitting this Notice."))
		if not self.reason_for_dismissals or not self.selection_method:
			frappe.throw(_("Pull the statutory disclosure fields from the Retrenchment Process before submitting."))
		self._validate_union_recipients()

	def _validate_union_recipients(self):
		from ir.industrial_relations.doctype.retrenchment_process.retrenchment_process import (
			get_union_membership_summary,
		)

		unions = get_union_membership_summary(self.linked_intervention)
		if not unions:
			return

		covered = {
			row.trade_union
			for row in self.recipients or []
			if row.recipient_type in ("Union Official", "Union Region") and row.trade_union
		}
		missing = [row["trade_union"] for row in unions if row["trade_union"] not in covered]
		if missing:
			frappe.throw(
				_(
					"The following Trade Union(s) have members among the affected employees and "
					"must be added as a Recipient (Union Official or Union Region) before "
					"submitting (s189): {0}."
				).format(", ".join(missing))
			)


@frappe.whitelist()
def fetch_from_process(retrenchment_process):
	from ir.industrial_relations.doctype.retrenchment_process.retrenchment_process import (
		get_designation_breakdown,
	)

	process = frappe.get_doc("Retrenchment Process", retrenchment_process)

	data = {field: process.get(field) for field in STATUTORY_FIELDS}

	branches = sorted({row.branch for row in (process.affected_employees or []) if row.branch})
	data["operation_description"] = ", ".join(f"{branch} Operation" for branch in branches)

	# Snapshot the (c) category breakdown at populate time - frozen onto this
	# Notice like every other statutory field, rather than derived live from
	# doc.recipients at print time (which would only ever show "current",
	# never "initial", and would silently drift if the Process changes later).
	data["designation_breakdown"] = [
		{
			"designation": row["designation"],
			"initial_count": row["initial"],
			"current_count": row["current"],
		}
		for row in get_designation_breakdown(retrenchment_process)
	]

	return data


@frappe.whitelist()
def get_union_officials(trade_union):
	"""Officials of `trade_union`, for the "Select Official / Region" picker -
	the Notice's Recipients table is hand-curated (no bulk auto-fill), so this
	just gives the picker something real to choose from."""
	return frappe.get_all(
		"Union Official",
		filters={"parent": trade_union, "parenttype": "Trade Union", "parentfield": "of_list"},
		fields=["name", "of_name", "of_pos", "of_mail"],
		order_by="idx asc",
	)


@frappe.whitelist()
def get_union_regions(trade_union):
	"""Regional/area offices of `trade_union`, for the same picker."""
	return frappe.get_all(
		"Union Region",
		filters={"parent": trade_union, "parenttype": "Trade Union", "parentfield": "region_list"},
		fields=["name", "region_name", "region_contact_name", "region_mail"],
		order_by="idx asc",
	)
