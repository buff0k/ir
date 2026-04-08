# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AnonymousReport(Document):
	def validate(self):
		if self.investigator:
			employee_name, designation = frappe.db.get_value(
				"Employee",
				self.investigator,
				["employee_name", "designation"]
			) or (None, None)

			self.investigator_name = employee_name or ""
			self.investigator_designation = designation or ""

		else:
			self.investigator_name = ""
			self.investigator_designation = ""

	def before_submit(self):
		if not self.investigator:
			frappe.throw("An Investigator must be allocated before submitting this document.")

		if not self.outcome:
			frappe.throw("Outcome is required before submitting this document.")