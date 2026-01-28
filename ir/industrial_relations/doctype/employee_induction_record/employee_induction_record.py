# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class EmployeeInductionRecord(Document):
	def before_submit(self):
		if not self.certificate:
			frappe.throw(
				_("You cannot submit this record without attaching the certificate file."),
				title=_("Certificate Required"),
			)