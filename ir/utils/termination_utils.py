"""
Termination & Settlement Utility Functions
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from ir.utils.statutory_rates import calculate_lump_sum_benefit_tax


def calculate_bcea_notice_period(employee, termination_date):
	"""BCEA minimum: 1 week under 6 months' tenure, 2 weeks from 6 months to
	a year, 4 weeks beyond that."""
	if isinstance(employee, str):
		employee = frappe.get_doc("Employee", employee)

	if not employee.date_of_joining:
		return 28

	tenure_days = date_diff(termination_date, employee.date_of_joining)
	tenure_years = tenure_days / 365.25

	if tenure_years < 0.5:
		return 7
	elif tenure_years < 1:
		return 14
	else:
		return 28


def calculate_severance_pay(employee, termination_date, termination_type):
	"""BCEA: 1 week's remuneration per completed year, operational dismissals only."""
	if termination_type != "Dismissal - Operational":
		return 0.0

	if isinstance(employee, str):
		employee = frappe.get_doc("Employee", employee)

	if not employee.date_of_joining:
		return 0.0

	tenure_days = date_diff(termination_date, employee.date_of_joining)
	completed_years = int(tenure_days / 365.25)

	if completed_years < 1:
		return 0.0

	salary = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee.name, "docstatus": 1},
		fields=["base"],
		order_by="from_date desc",
		limit=1
	)

	if not salary:
		return 0.0

	monthly_salary = flt(salary[0].base)
	weekly_salary = monthly_salary / 4.33  # average weeks per month

	return weekly_salary * completed_years


def calculate_leave_payout_on_termination(employee):
	"""For untaken annual leave."""
	leave_balance = frappe.db.sql("""
		SELECT SUM(total_leave_days) as balance
		FROM `tabLeave Allocation`
		WHERE employee = %(employee)s
			AND docstatus = 1
			AND leave_type LIKE '%%Annual%%'
	""", {"employee": employee}, as_dict=1)

	if not leave_balance or not leave_balance[0].balance:
		return {"days": 0, "amount": 0}

	total_days = flt(leave_balance[0].balance)

	salary = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee, "docstatus": 1},
		fields=["base"],
		order_by="from_date desc",
		limit=1
	)

	if not salary:
		return {"days": total_days, "amount": 0}

	monthly_salary = flt(salary[0].base)
	daily_rate = monthly_salary / 30

	return {
		"days": total_days,
		"amount": daily_rate * total_days
	}


def calculate_severance_tax(severance_amount, date_value=None, previous_lump_sums=0):
	"""SARS taxes severance using the retirement fund lump sum benefits
	table, on a cumulative basis."""
	return calculate_lump_sum_benefit_tax(
		severance_amount,
		date_value=date_value,
		previous_lump_sums=previous_lump_sums,
	)
