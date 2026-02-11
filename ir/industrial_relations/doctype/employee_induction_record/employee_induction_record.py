# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import formatdate

def _clean(s: str) -> str:
	return re.sub(r"\s+", " ", (s or "").strip())


class EmployeeInductionRecord(Document):
	def autoname(self):
		training_date = formatdate(self.training_date, "dd-MM-yyyy") if self.training_date else ""
		name = f"{self.employee} - {self.training} - {training_date}"
		self.name = _clean(name)

        # Duplicate check
		if frappe.db.exists(self.doctype, self.name):
			frappe.throw(
				f"Duplicate record: an Employee Induction Record already exists for "
				f"{self.employee}, {self.training} on {training_date}."
			)

	def before_submit(self):
		if not self.certificate:
			frappe.throw(
				_("You cannot submit this record without attaching the certificate file."),
				title=_("Certificate Required"),
			)