# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from ir.industrial_relations import utils


class S189Consultation(Document):
	def autoname(self):
		utils.autoname_by_linked_parent(self, "S189-CONSULT")

	def validate(self):
		if not self.ir_intervention:
			self.ir_intervention = "Retrenchment Process"

	def before_submit(self):
		if not self.attendees:
			frappe.throw(_("Add at least one Attendee before submitting this Consultation."))


@frappe.whitelist()
def populate_attendees(retrenchment_process):
	process = frappe.get_doc("Retrenchment Process", retrenchment_process)

	attendees = []
	for row in process.affected_employees or []:
		if not row.employee or (row.inclusion_status and row.inclusion_status != "Affected") or row.outcome:
			continue
		attendees.append(
			{
				"attendee_type": "Employee",
				"employee": row.employee,
				"employee_name": row.employee_name,
				"represented_by": "Self",
			}
		)

	return attendees


@frappe.whitelist()
def populate_union_attendees(retrenchment_process):
	from ir.industrial_relations.doctype.retrenchment_process.retrenchment_process import (
		get_union_membership_summary,
	)

	rows = []
	for union in get_union_membership_summary(retrenchment_process):
		officials = union["officials"]
		primary = officials[0] if officials else {}
		rows.append(
			{
				"attendee_type": "Trade Union",
				"trade_union": union["trade_union"],
				"contact_name": primary.get("of_name") or "",
			}
		)

	return rows
