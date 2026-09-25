# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Retrenchment cost estimation - notice pay, severance pay, and leave payout
per Affected Employee, replicating a real spreadsheet this team already uses
(IS_BNK_CALC.xlsx) but generalised in two ways the workbook itself couldn't
be, per the user:

1. Allowances are an open-ended, per-employee list (Retrenchment Employee
   Allowance, a sibling child table on Retrenchment Process - Frappe has no
   nested child tables, so this can't live inside Retrenchment Affected
   Employee itself), not a fixed set of named columns - different
   sites/designations carry different allowances.
2. Several of the workbook's own hardcoded numbers (9 hours/day, 45 severance
   hours/week) are real, negotiable/variable terms, not universal constants -
   hours/day varies by site/designation, and severance terms
   (weeks-per-completed-year, the hourly "week" definition, a minimum-weeks
   floor) get negotiated per process and are exposed as real fields rather
   than literals.

Rate/allowance/leave fetch (get_employee_cost_inputs) targets Salary Structure
Assignment / Salary Slip / Leave Balance - the correct, "Normal Way" sources -
even though none of the first two have any submitted records in this system
yet, and Leave Allocation has no baseline. That's fine: this returns blanks
until real payroll/leave data exists, and the user fills the row in by hand
until then - not a special case, just what "pull once, allow override" means
before go-live.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

DAYS_PER_MONTH = 21.66667  # average working days/month - a calendar fact, not negotiated (195 / 9, matching the workbook's own hours_per_month / hours_per_day ratio)
WEEKS_PER_MONTH = 4.333
LEAVE_TYPE_FOR_PAYOUT = "Annual Leave"


@frappe.whitelist()
def get_employee_cost_inputs(employee):
	"""Best-effort fetch of this employee's current rate, allowances, and leave
	balance from real Payroll/Leave data - returns blanks for anything not yet
	live (no submitted Assignment/Slip, no Leave Allocation), by design."""
	rate_per_hour = None
	allowances = []

	slip = frappe.get_all(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["name"],
		order_by="posting_date desc, creation desc",
		limit_page_length=1,
	)

	assignment = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "base", "salary_structure"],
		order_by="from_date desc",
		limit_page_length=1,
	)
	if assignment:
		rate_per_hour = flt(assignment[0].base)

	if slip:
		# Actual amounts paid, when available - the most authoritative source.
		allowances = frappe.get_all(
			"Salary Detail",
			filters={"parent": slip[0].name, "parenttype": "Salary Slip", "parentfield": "earnings"},
			fields=["salary_component", "amount"],
		)
	elif assignment and assignment[0].salary_structure:
		# No Slip yet - fall back to the assigned Structure's own flat
		# (non-formula) component amounts. Formula-driven components are
		# skipped rather than evaluated - we don't have the context (payroll
		# period, attendance, etc.) to do that safely here.
		allowances = frappe.get_all(
			"Salary Detail",
			filters={
				"parent": assignment[0].salary_structure,
				"parenttype": "Salary Structure",
				"parentfield": "earnings",
				"amount_based_on_formula": 0,
			},
			fields=["salary_component", "amount"],
		)

	leave_days_balance = 0
	try:
		from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

		balance = get_leave_balance_on(employee, LEAVE_TYPE_FOR_PAYOUT, getdate(today()))
		leave_days_balance = flt(balance)
	except Exception:
		frappe.log_error(title="get_employee_cost_inputs: leave balance lookup failed")

	return {
		"rate_per_hour": rate_per_hour,
		"allowances": [{"salary_component": row.salary_component, "amount": flt(row.amount)} for row in allowances],
		"leave_days_balance": leave_days_balance,
	}


def compute_row_costs(row, total_allowances, severance_terms):
	"""Pure function: one Retrenchment Affected Employee row + its allowance
	total + the effective severance terms (process defaults or this row's own
	overrides) -> the 9 computed fields, replicating the workbook's formulas
	(see module docstring for what's been generalised)."""
	rate_per_hour = flt(row.rate_per_hour)
	hours_per_day = flt(row.hours_per_day) or 9

	result = {
		"total_allowances": flt(total_allowances),
		"thirty_days_date": None,
		"completed_years": 0,
		"notice_weeks": 0,
		"notice_ends_date": None,
		"weekly_rate": 0.0,
		"estimated_leave_pay": 0.0,
		"estimated_notice_pay": 0.0,
		"estimated_severance_pay": 0.0,
		"estimated_total_cost": 0.0,
	}

	if row.s189_notice_date and row.date_of_joining:
		thirty_days_date = add_days(getdate(row.s189_notice_date), 30)
		result["thirty_days_date"] = thirty_days_date

		completed_years = _datediff_years(getdate(row.date_of_joining), thirty_days_date)
		result["completed_years"] = completed_years

		if completed_years >= 1:
			notice_weeks = 4
		elif _datediff_months(getdate(row.date_of_joining), thirty_days_date) >= 6:
			notice_weeks = 2
		else:
			notice_weeks = 0
		result["notice_weeks"] = notice_weeks
		result["notice_ends_date"] = add_days(thirty_days_date, notice_weeks * 7)

		hours_per_month = hours_per_day * DAYS_PER_MONTH
		weekly_rate = (rate_per_hour * hours_per_month + flt(total_allowances)) / WEEKS_PER_MONTH
		result["weekly_rate"] = weekly_rate
		result["estimated_notice_pay"] = weekly_rate * notice_weeks

		weeks_per_year = flt(severance_terms.get("severance_weeks_per_completed_year")) or 1
		hours_per_week = flt(severance_terms.get("severance_hours_per_week")) or 45
		minimum_weeks = flt(severance_terms.get("minimum_severance_weeks"))
		effective_weeks = max(completed_years * weeks_per_year, minimum_weeks)
		result["estimated_severance_pay"] = effective_weeks * hours_per_week * rate_per_hour

	leave_days_projected = flt(row.leave_days_projected)
	result["estimated_leave_pay"] = rate_per_hour * hours_per_day * leave_days_projected

	result["estimated_total_cost"] = (
		result["estimated_notice_pay"] + result["estimated_severance_pay"] + result["estimated_leave_pay"]
	)
	return result


def _datediff_years(from_date, to_date):
	years = to_date.year - from_date.year
	if (to_date.month, to_date.day) < (from_date.month, from_date.day):
		years -= 1
	return max(years, 0)


def _datediff_months(from_date, to_date):
	months = (to_date.year - from_date.year) * 12 + (to_date.month - from_date.month)
	if to_date.day < from_date.day:
		months -= 1
	return max(months, 0)


def _apply_costing(doc):
	allowance_totals = {}
	for row in doc.employee_allowances or []:
		allowance_totals[row.employee] = allowance_totals.get(row.employee, 0) + flt(row.amount)

	process_terms = {
		"severance_weeks_per_completed_year": doc.severance_weeks_per_completed_year,
		"severance_hours_per_week": doc.severance_hours_per_week,
		"minimum_severance_weeks": doc.minimum_severance_weeks,
	}

	total_cost = 0.0
	for row in doc.affected_employees or []:
		if not row.employee:
			continue

		row_terms = {
			"severance_weeks_per_completed_year": row.severance_weeks_per_completed_year or process_terms["severance_weeks_per_completed_year"],
			"severance_hours_per_week": row.severance_hours_per_week or process_terms["severance_hours_per_week"],
			"minimum_severance_weeks": row.minimum_severance_weeks or process_terms["minimum_severance_weeks"],
		}

		computed = compute_row_costs(row, allowance_totals.get(row.employee, 0), row_terms)
		for fieldname, value in computed.items():
			row.set(fieldname, value)

		total_cost += computed["estimated_total_cost"]

	doc.estimated_total_retrenchment_cost = total_cost
