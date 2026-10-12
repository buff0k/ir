# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate


class IRSalaryStructure(Document):
	def autoname(self):
		if not self.company:
			frappe.throw(_("Company is required before naming."))
		if not self.branch:
			frappe.throw(_("Branch is required before naming."))
		if not self.start_date:
			frappe.throw(_("Valid From is required before naming."))

		# ISO (yyyy-mm-dd) so the name also sorts chronologically within a
		# Company/Branch group - same convention used by Bargaining Unit's
		# autoname().
		formatted_date = formatdate(self.start_date, "yyyy-mm-dd")
		candidate_name = f"{self.company} - {self.branch} - {formatted_date}"

		if frappe.db.exists(self.doctype, candidate_name):
			frappe.throw(
				_(
					"An IR Salary Structure named {0} already exists. Change the Valid "
					"From date, or amend the existing record instead."
				).format(frappe.bold(candidate_name)),
				title=_("Duplicate IR Salary Structure"),
			)

		self.name = candidate_name


@frappe.whitelist()
def get_company_letter_head(company):
	if not company:
		return None
	return frappe.db.get_value("Company", company, "default_letter_head")


@frappe.whitelist()
def get_salary_structure_summaries(names):
	if isinstance(names, str):
		names = frappe.parse_json(names)
	names = list({n for n in (names or []) if n})
	if not names:
		return {}

	rows = frappe.get_all(
		"Salary Structure",
		filters={"name": ["in", names]},
		fields=[
			"name",
			"is_active",
			"payroll_frequency",
			"currency",
			"total_earning",
			"total_deduction",
			"net_pay",
		],
	)
	return {r.name: r for r in rows}
