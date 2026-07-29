# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import formatdate, getdate


class SiteBudgetMap(Document):
	def autoname(self):
		parts = [
			self.company,
			self.branch,
			self.designation,
			formatdate(self.start_date, "yyyy-mm-dd") if self.start_date else "",
		]
		base = " - ".join(part for part in parts if part)
		if frappe.db.exists("Site Budget Map", base):
			base = append_number_if_name_exists("Site Budget Map", base)
		self.name = base

	def before_submit(self):
		self.validate_no_overlapping_active_map()

	def validate_no_overlapping_active_map(self):
		candidates = frappe.get_all(
			"Site Budget Map",
			filters={
				"designation": self.designation,
				"company": self.company or "",
				"branch": self.branch or "",
				"docstatus": 1,
				"name": ["!=", self.name],
			},
			fields=["name", "start_date", "end_date"],
		)
		for row in candidates:
			if _date_ranges_overlap(self.start_date, self.end_date, row.start_date, row.end_date):
				frappe.throw(
					_("{0} already has an active Site Budget Map ({1}) covering this period.").format(
						self.designation, row.name
					)
				)


def _date_ranges_overlap(start_a, end_a, start_b, end_b):
	if end_a and start_b and getdate(end_a) < getdate(start_b):
		return False
	if end_b and start_a and getdate(end_b) < getdate(start_a):
		return False
	return True


@frappe.whitelist()
def get_salary_structure_preview(salary_structure):
	if not salary_structure:
		return ""

	ss = frappe.get_doc("Salary Structure", salary_structure)
	has_formula_component = False

	def rows(components):
		nonlocal has_formula_component
		out = ""
		fixed_total = 0
		for row in components:
			if row.amount_based_on_formula:
				has_formula_component = True
				value = frappe.utils.escape_html(row.formula or "")
			else:
				fixed_total += row.amount or 0
				value = frappe.utils.fmt_money(row.amount, currency=ss.currency)
			out += f"<tr><td>{frappe.utils.escape_html(row.salary_component)}</td><td>{value}</td></tr>"
		return out, fixed_total

	earning_rows, total_earning = rows(ss.earnings)
	deduction_rows, total_deduction = rows(ss.deductions)
	net_pay = total_earning - total_deduction
	note = (
		"<p class=\"text-muted small\">Totals exclude formula-based components, which are computed at payroll time.</p>"
		if has_formula_component
		else ""
	)

	html = f"""
	<div class="salary-structure-preview">
		<table class="table table-bordered">
			<thead>
				<tr><th>Component</th><th>Amount / Formula</th></tr>
			</thead>
			<tbody>
				<tr class="text-muted"><td colspan="2"><strong>Earnings</strong></td></tr>
				{earning_rows}
				<tr class="text-muted"><td colspan="2"><strong>Deductions</strong></td></tr>
				{deduction_rows}
			</tbody>
			<tfoot>
				<tr><td><strong>Total Earning</strong></td><td>{frappe.utils.fmt_money(total_earning, currency=ss.currency)}</td></tr>
				<tr><td><strong>Total Deduction</strong></td><td>{frappe.utils.fmt_money(total_deduction, currency=ss.currency)}</td></tr>
				<tr><td><strong>Net Pay</strong></td><td>{frappe.utils.fmt_money(net_pay, currency=ss.currency)}</td></tr>
			</tfoot>
		</table>
		{note}
	</div>
	"""
	return html
