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
			row.trade_union for row in self.recipients or [] if row.recipient_type == "Trade Union" and row.trade_union
		}
		missing = [row["trade_union"] for row in unions if row["trade_union"] not in covered]
		if missing:
			frappe.throw(
				_(
					"The following Trade Union(s) have members among the affected employees and "
					"must be added as Trade Union Recipients before submitting (s189): {0}. Use "
					"\"Populate Union Recipients\"."
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
def populate_recipients(retrenchment_process):
	process = frappe.get_doc("Retrenchment Process", retrenchment_process)

	recipients = []
	skipped = 0
	for row in process.affected_employees or []:
		if not row.employee or (row.inclusion_status and row.inclusion_status != "Affected") or row.outcome:
			skipped += 1
			continue
		recipients.append(
			{
				"recipient_type": "Employee",
				"employee": row.employee,
				"employee_name": row.employee_name,
				"branch": row.branch,
			}
		)

	if skipped:
		frappe.msgprint(
			_(
				"{0} row(s) on the Retrenchment Process were skipped - either they have no "
				"named Employee yet (category-only slots), they're marked Excluded/Transferred, "
				"or they've already been dismissed."
			).format(skipped),
			indicator="orange",
			alert=True,
		)

	return recipients


@frappe.whitelist()
def populate_union_recipients(retrenchment_process):
	from ir.industrial_relations.doctype.retrenchment_process.retrenchment_process import (
		get_union_membership_summary,
	)

	rows = []
	for union in get_union_membership_summary(retrenchment_process):
		officials = union["officials"]
		primary = officials[0] if officials else {}
		rows.append(
			{
				"recipient_type": "Trade Union",
				"trade_union": union["trade_union"],
				"contact_name": primary.get("of_name") or "",
				"contact_email": primary.get("of_mail") or "",
			}
		)

	return rows
