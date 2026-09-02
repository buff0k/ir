# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import formatdate

from ir.industrial_relations.utils import fetch_company_letter_head as _fetch_company_letter_head

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


@frappe.whitelist()
def fetch_company_letter_head(company):
	return _fetch_company_letter_head(company)


@frappe.whitelist()
def get_ofo_codes_for_designation(designation):
	"""OFO Code names whose Designation Selector child table includes
	`designation`. Deliberately not a plain frappe.db.get_list("Designation
	Selector", ...) call from the client - Designation Selector is a child
	table (istable=1) with no permission rules of its own (child tables don't
	need any for the normal case, access via their parent), but the generic
	list API still enforces frappe.has_permission on whatever doctype it's
	asked for, so querying it directly like a top-level doctype always denied
	every non-System-Manager user outright ("Insufficient Permission for
	Designation Selector"). Gate on the real doctype being looked up instead
	(Organising Framework for Occupation Code) and read the child rows with
	ignore_permissions, since nothing here exposes anything beyond the parent
	OFO Code names a caller who can read that doctype could already list."""
	frappe.has_permission("Organising Framework for Occupation Code", "read", throw=True)

	if not designation:
		return []

	rows = frappe.get_all(
		"Designation Selector",
		filters={"designation": designation, "parenttype": "Organising Framework for Occupation Code"},
		fields=["parent"],
		limit_page_length=50,
		ignore_permissions=True,
	)
	return sorted({row.parent for row in rows if row.parent})