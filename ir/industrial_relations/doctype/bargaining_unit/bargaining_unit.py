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
