# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate


class BargainingUnit(Document):
	def autoname(self):
		if not self.company:
			frappe.throw(_("Company is required before naming."))
		if not self.bu_name:
			frappe.throw(_("Bargaining Unit Name is required before naming."))
		if not self.create_date:
			frappe.throw(_("Inception Date is required before naming."))

		# ISO (yyyy-mm-dd) so the name also sorts chronologically within a
		# Company/Bargaining Unit Name group, same convention used by
		# autoname_planning_document() elsewhere in this app.
		formatted_date = formatdate(self.create_date, "yyyy-mm-dd")
		candidate_name = f"{self.company}-{(self.bu_name or '').strip()}-{formatted_date}"

		if frappe.db.exists(self.doctype, candidate_name):
			frappe.throw(
				_(
					"A Bargaining Unit named {0} already exists for Company {1} with "
					"Inception Date {2}. Change the Bargaining Unit Name, Company or "
					"Inception Date to create a distinct record."
				).format(
					frappe.bold(self.bu_name), frappe.bold(self.company), frappe.bold(formatted_date)
				),
				title=_("Duplicate Bargaining Unit"),
			)

		self.name = candidate_name

	def validate(self):
		self.check_designation_conflicts()

	def check_designation_conflicts(self):
		# A Bargaining Unit only "exists" once submitted, so a Designation is
		# only a real conflict if it's already sitting in another SUBMITTED
		# Bargaining Unit - a draft overlapping a draft is just work in
		# progress. This mirrors the live, per-row check in bargaining_unit.js
		# and acts as the backstop for bulk edit / Data Import / API inserts,
		# which never go through that client-side check.
		for row in self.applicable_designations:
			if not row.designation:
				continue
			conflict = find_conflicting_bargaining_unit(row.designation, exclude=self.name)
			if conflict:
				frappe.throw(
					_(
						"Designation {0} is already assigned to the submitted Bargaining "
						"Unit {1}. A Designation cannot belong to more than one Bargaining "
						"Unit."
					).format(frappe.bold(row.designation), frappe.bold(conflict)),
					title=_("Designation Conflict"),
				)


@frappe.whitelist()
def find_conflicting_bargaining_unit(designation, exclude=None):
	"""Name of a SUBMITTED Bargaining Unit (other than `exclude`) that already
	carries this designation, or None if there is no conflict."""
	if not designation:
		return None

	rows = frappe.get_all(
		"Designation Selector",
		filters={
			"parenttype": "Bargaining Unit",
			"parentfield": "applicable_designations",
			"designation": designation,
		},
		fields=["parent"],
	)
	parents = {r.parent for r in rows if r.parent != exclude}
	if not parents:
		return None

	submitted = frappe.get_all(
		"Bargaining Unit",
		filters={"name": ["in", list(parents)], "docstatus": 1},
		pluck="name",
		limit=1,
	)
	return submitted[0] if submitted else None
