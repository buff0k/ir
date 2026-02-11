# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document

def _clean(s: str) -> str:
	return re.sub(r"\s+", " ", (s or "").strip())


class EmployeeInductionTracking(Document):
	def autoname(self):
		name = f"{self.employee} - {self.branch}"
		self.name = _clean(name)
		# Duplicate check
		if frappe.db.exists(self.doctype, self.name):
			frappe.throw(
				f"Duplicate record: an entry already exists for {self.employee} at {self.branch}."
			)
