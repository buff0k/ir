# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import flt, formatdate, getdate


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


def resolve_active_site_budget_map(branch, designation, on_date):
	"""The Submitted Site Budget Map (if any) covering `designation` at
	`branch`, active as of `on_date` (start_date <= on_date, end_date blank
	or >= on_date). Shared by Site Budget's default-population (which just
	needs the salary_structure) and its cost calculation (which also needs
	this to attribute Site Specific Allowances - see get_site_budget_summary_html).
	Returns the matched row (name, salary_structure, end_date) or None.
	"""
	if not on_date:
		return None

	candidates = frappe.get_all(
		"Site Budget Map",
		filters={
			"designation": designation,
			"branch": branch or "",
			"docstatus": 1,
			"start_date": ["<=", on_date],
		},
		fields=["name", "salary_structure", "end_date"],
		order_by="start_date desc",
	)

	for row in candidates:
		if not row.end_date or getdate(row.end_date) >= getdate(on_date):
			return row

	return None


def compute_salary_structure_totals(salary_structure):
	"""Salary Structure's own total_earning/total_deduction/net_pay fields
	are hidden, read_only, and never populated by its controller - the only
	real totals come from summing its Earnings/Deductions rows ourselves.
	Formula-based rows are excluded (payroll-time only) and flagged via
	has_formula_component so callers can note the total is incomplete.

	total_earning/net_pay here are the FIXED portion only - they deliberately
	exclude the timesheet-based hourly earning (salary_slip_based_on_timesheet
	+ salary_component + hour_rate), since that's a rate, not a static amount,
	computed at payslip time from actual/approved timesheet hours. hour_rate/
	salary_component/salary_slip_based_on_timesheet are passed through raw so
	callers with hours context (e.g. Site Budget, which knows each role's
	Shift Design and its Ordinary Hours Limit) can fold the hourly portion in
	themselves.
	"""
	ss = frappe.get_doc("Salary Structure", salary_structure)
	has_formula_component = False

	def sum_fixed(components):
		nonlocal has_formula_component
		total = 0
		for row in components:
			if row.amount_based_on_formula:
				has_formula_component = True
			else:
				total += row.amount or 0
		return total

	total_earning = sum_fixed(ss.earnings)
	total_deduction = sum_fixed(ss.deductions)

	return {
		"total_earning": total_earning,
		"total_deduction": total_deduction,
		"net_pay": total_earning - total_deduction,
		"has_formula_component": has_formula_component,
		"currency": ss.currency,
		"salary_slip_based_on_timesheet": bool(ss.salary_slip_based_on_timesheet),
		"salary_component": ss.salary_component,
		"hour_rate": ss.hour_rate or 0,
	}


def compute_site_budget_map_totals(site_budget_map):
	"""Combines the base Salary Structure totals with this mapping's own
	Site Specific Allowances (a flat sum - allowances are simple top-up
	amounts, not formula-based like some Salary Structure rows can be).
	Returns the base totals plus `allowances_total` and a combined `net_pay`.
	"""
	doc = frappe.get_doc("Site Budget Map", site_budget_map)
	totals = compute_salary_structure_totals(doc.salary_structure) if doc.salary_structure else {
		"total_earning": 0,
		"total_deduction": 0,
		"net_pay": 0,
		"has_formula_component": False,
		"currency": None,
		"salary_slip_based_on_timesheet": False,
		"salary_component": None,
		"hour_rate": 0,
	}

	allowances_total = sum(row.amount or 0 for row in doc.site_specific_allowances or [])

	return {
		**totals,
		"allowances_total": allowances_total,
		"net_pay": totals["net_pay"] + allowances_total,
	}


@frappe.whitelist()
def get_site_budget_map_preview(salary_structure, site_specific_allowances=None):
	"""Renders purely from the arguments given - not from a persisted Site
	Budget Map record - so the client can call this live as the user picks a
	Salary Structure or edits the Site Specific Allowances grid, before ever
	saving the form (see site_budget_map.js).
	"""
	if not salary_structure:
		return ""

	site_specific_allowances = frappe.parse_json(site_specific_allowances) or []

	ss = frappe.get_doc("Salary Structure", salary_structure)
	totals = compute_salary_structure_totals(salary_structure)
	allowances_total = sum(flt(row.get("amount")) for row in site_specific_allowances)
	net_pay = totals["net_pay"] + allowances_total

	def rows(components):
		out = ""
		for row in components:
			if row.amount_based_on_formula:
				value = frappe.utils.escape_html(row.formula or "")
			else:
				value = frappe.utils.fmt_money(row.amount, currency=ss.currency)
			out += f"<tr><td>{frappe.utils.escape_html(row.salary_component)}</td><td>{value}</td></tr>"
		return out

	earning_rows = rows(ss.earnings)
	if totals["salary_slip_based_on_timesheet"]:
		# Hourly Earnings isn't a row in the Earnings table at all (it's
		# computed from hour_rate x timesheet hours, not a fixed amount) -
		# shown alongside the real Earnings rows, styled like a formula row
		# (a rate, not a money amount), rather than as its own section.
		earning_rows += (
			f'<tr><td>{frappe.utils.escape_html(totals["salary_component"] or "")}</td>'
			f'<td>{frappe.utils.fmt_money(totals["hour_rate"], currency=ss.currency)} / hour</td></tr>'
		)

	deduction_rows = rows(ss.deductions)

	notes = []
	if totals["has_formula_component"]:
		notes.append("Totals exclude formula-based components, which are computed at payroll time.")
	if totals["salary_slip_based_on_timesheet"]:
		notes.append(
			"This Salary Structure is timesheet-based - the hourly rate above is not included in "
			"Total Earning/Net Pay, since it depends on hours worked. Site Budget's own cost "
			"prediction estimates it using the linked Shift Design's Ordinary Hours Limit."
		)
	note_html = "".join(f'<p class="text-muted small">{n}</p>' for n in notes)

	allowance_rows = "".join(
		f"<tr><td>{frappe.utils.escape_html(row.get('salary_component') or '')}</td>"
		f"<td>{frappe.utils.fmt_money(flt(row.get('amount')), currency=ss.currency)}</td></tr>"
		for row in site_specific_allowances
	)
	allowances_section = (
		f"""
		<tr class="text-muted"><td colspan="2"><strong>Site Specific Allowances</strong></td></tr>
		{allowance_rows}
		"""
		if site_specific_allowances
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
				{allowances_section}
			</tbody>
			<tfoot>
				<tr><td><strong>Total Earning</strong></td><td>{frappe.utils.fmt_money(totals["total_earning"], currency=ss.currency)}</td></tr>
				<tr><td><strong>Total Deduction</strong></td><td>{frappe.utils.fmt_money(totals["total_deduction"], currency=ss.currency)}</td></tr>
				<tr><td><strong>Site Specific Allowances</strong></td><td>{frappe.utils.fmt_money(allowances_total, currency=ss.currency)}</td></tr>
				<tr><td><strong>Combined Net Pay (excl. hourly pay)</strong></td><td>{frappe.utils.fmt_money(net_pay, currency=ss.currency)}</td></tr>
			</tfoot>
		</table>
		{note_html}
	</div>
	"""
	return html
