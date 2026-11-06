"""
South African Tax Utility Functions

This module provides utility functions for South African tax calculations including:
- PAYE (Pay As You Earn) calculations
- Tax rebates (primary, secondary, tertiary)
- Medical aid tax credits
- Retirement annuity deductions
"""

import calendar
from datetime import date

import frappe
from frappe.utils import date_diff, flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import calculate_tax_by_tax_slab

from ir.utils.statutory_rates import (
	get_retirement_annual_cap,
	get_retirement_deduction_percentage,
	get_sdl_rate,
	get_uif_employee_rate,
	get_uif_employer_rate,
	get_uif_monthly_cap,
)


def calculate_south_african_tax(
	annual_taxable_income,
	tax_slab=None,
	date_value=None,
	company=None,
):
	"""Calculate annual PAYE using the slab effective for the supplied date."""
	if flt(annual_taxable_income) <= 0:
		return 0

	if not tax_slab:
		tax_slab = get_current_tax_slab(date_value=date_value, company=company)
	elif isinstance(tax_slab, str):
		tax_slab = frappe.get_cached_doc("Income Tax Slab", tax_slab)

	if not tax_slab:
		frappe.throw(
			frappe._("No submitted Income Tax Slab is configured for {0}.").format(
				getdate(date_value or frappe.utils.today())
			),
			title=frappe._("Missing Income Tax Slab"),
		)

	tax_amount, _other_taxes_and_charges = calculate_tax_by_tax_slab(
		annual_taxable_income,
		tax_slab,
		eval_globals=None,
		eval_locals={},
	)
	return flt(tax_amount)


def get_current_tax_slab(date_value=None, company=None):
	"""Return the submitted slab effective on ``date_value`` for ``company``."""
	date_value = getdate(date_value or frappe.utils.today())
	base_filters = {
		"disabled": 0,
		"docstatus": 1,
		"effective_from": ["<=", date_value],
	}
	company_filters = [company, ["is", "not set"]] if company else [["is", "not set"]]
	for company_filter in company_filters:
		filters = {**base_filters, "company": company_filter}
		name = frappe.db.get_value(
			"Income Tax Slab",
			filters,
			"name",
			order_by="effective_from desc",
		)
		if name:
			return frappe.get_cached_doc("Income Tax Slab", name)
	return None


def _get_payroll_period_name(salary_slip):
	date_value = getdate(salary_slip.end_date)
	company = getattr(salary_slip, "company", None)
	if not company:
		frappe.throw(
			frappe._("Salary Slip company is required to resolve statutory tax rates."),
			title=frappe._("Missing Company"),
		)

	period = frappe.db.get_value(
		"Payroll Period",
		{
			"company": company,
			"start_date": ["<=", date_value],
			"end_date": [">=", date_value],
		},
		"name",
		order_by="start_date desc",
	)
	if not period:
		frappe.throw(
			frappe._("No Payroll Period covers {0} for company {1}.").format(date_value, company),
			title=frappe._("Missing Payroll Period"),
		)
	return period


def _get_statutory_rate_row(rows, payroll_period, rate_label):
	for row in rows or []:
		if row.get("payroll_period") == payroll_period:
			return row
	frappe.throw(
		frappe._("No {0} row is configured for Payroll Period {1}.").format(rate_label, payroll_period),
		title=frappe._("Missing Statutory Rate"),
	)


def get_tax_rebate(salary_slip, date_of_birth):
	"""Primary rebate applies to everyone; secondary adds on at 65, tertiary
	at 75 - rates themselves come from Tax Rebates and Medical Tax Credit,
	not hardcoded here."""
	if not date_of_birth:
		return 0

	rebate_settings = frappe.get_single("Tax Rebates and Medical Tax Credit")
	if not rebate_settings.tax_rebates_rate:
		frappe.throw(
			frappe._("Tax rebate rates are not configured."),
			title=frappe._("Missing Tax Rebate Rates"),
		)

	dob = getdate(date_of_birth)
	_start_date, tax_year_end = get_tax_year_dates(getdate(salary_slip.end_date))
	year_end = getdate(tax_year_end)

	age = year_end.year - dob.year
	if (year_end.month, year_end.day) < (dob.month, dob.day):
		age -= 1

	rebate = _get_statutory_rate_row(
		rebate_settings.tax_rebates_rate,
		_get_payroll_period_name(salary_slip),
		frappe._("tax rebate"),
	)
	total_rebate = flt(rebate.primary)
	if age >= 65:
		total_rebate += flt(rebate.secondary)
	if age >= 75:
		total_rebate += flt(rebate.tertiary)
	return total_rebate


def get_medical_aid_credit(
	salary_slip,
	number_of_dependants,
	membership_start_date=None,
	membership_end_date=None,
):
	"""Medical Tax Credit Rate's fields are named one off from what they mean:
	one_dependant is the main member's own rate, two_dependant is the first
	actual dependant, and additional_dependant covers every one after that."""
	if number_of_dependants < 0:
		return 0

	credit_settings = frappe.get_single("Tax Rebates and Medical Tax Credit")
	if not credit_settings.medical_tax_credit:
		frappe.throw(
			frappe._("Medical tax credit rates are not configured."),
			title=frappe._("Missing Medical Tax Credit Rates"),
		)

	credit = _get_statutory_rate_row(
		credit_settings.medical_tax_credit,
		_get_payroll_period_name(salary_slip),
		frappe._("medical tax credit"),
	)
	monthly_credit = flt(credit.one_dependant)
	if number_of_dependants >= 1:
		monthly_credit += flt(credit.two_dependant)
	if number_of_dependants >= 2:
		monthly_credit += flt(credit.additional_dependant) * (number_of_dependants - 1)

	tax_year_start, tax_year_end = get_tax_year_dates(getdate(salary_slip.end_date))
	credit_start = max(tax_year_start, getdate(membership_start_date or tax_year_start))
	credit_end = min(tax_year_end, getdate(membership_end_date or tax_year_end))
	if credit_end < credit_start:
		return 0
	qualifying_months = min(
		12,
		(credit_end.year - credit_start.year) * 12 + credit_end.month - credit_start.month + 1,
	)
	return monthly_credit * qualifying_months


def calculate_retirement_annuity_deduction(salary_slip, retirement_contribution):
	"""Capped to the lowest of: actual contribution, the statutory percentage
	of taxable income, and the statutory annual limit (both date-effective,
	see get_retirement_deduction_percentage/get_retirement_annual_cap)."""
	if not retirement_contribution or retirement_contribution <= 0:
		return 0

	date_value = getattr(salary_slip, "end_date", None)
	max_percentage = get_retirement_deduction_percentage(date_value)
	max_annual_limit = get_retirement_annual_cap(date_value)

	taxable_income = flt(salary_slip.total_taxable_earnings)
	max_by_percentage = taxable_income * max_percentage

	return min(retirement_contribution, max_by_percentage, max_annual_limit)


def calculate_uif_contribution(gross_pay, date_value=None):
	"""Returns (employee_uif, employer_uif); rates and the monthly cap are
	date-effective, not hardcoded here."""
	UIF_MAX_MONTHLY = get_uif_monthly_cap(date_value)
	employee_rate = get_uif_employee_rate(date_value)
	employer_rate = get_uif_employer_rate(date_value)

	capped_gross = min(flt(gross_pay), UIF_MAX_MONTHLY)
	employee_uif = capped_gross * employee_rate
	employer_uif = capped_gross * employer_rate

	return (employee_uif, employer_uif)


def calculate_sdl_contribution(gross_pay, date_value=None):
	"""Employer-paid Skills Development Levy; rate is date-effective."""
	return flt(gross_pay) * get_sdl_rate(date_value)


def validate_south_african_id_number(id_number):
	"""Format is YYMMDD SSSS CAZ: date of birth, gender (0000-4999 Female,
	5000-9999 Male), citizenship (0 SA citizen, 1 Permanent resident), an
	A digit that's usually 8 or 9, and a Luhn checksum digit."""
	if not id_number or len(id_number) != 13 or not id_number.isdigit():
		return None

	yy = int(id_number[0:2])
	mm = int(id_number[2:4])
	dd = int(id_number[4:6])
	gender_code = int(id_number[6:10])
	citizenship_code = int(id_number[10])
	checksum = int(id_number[12])

	if mm < 1 or mm > 12 or dd < 1 or dd > 31:
		return None

	current_year = date.today().year % 100
	century = 1900 if yy > current_year else 2000
	year = century + yy

	try:
		dob = date(year, mm, dd)
	except ValueError:
		return None

	total = 0
	for i, digit in enumerate(id_number[:-1]):
		num = int(digit)
		if i % 2 == 0:
			total += num
		else:
			doubled = num * 2
			total += doubled if doubled <= 9 else doubled - 9

	calculated_checksum = (10 - (total % 10)) % 10

	if calculated_checksum != checksum:
		return None

	gender = "Female" if gender_code < 5000 else "Male"
	citizenship = "SA Citizen" if citizenship_code == 0 else "Permanent Resident"

	return {
		"valid": True,
		"gender": gender,
		"date_of_birth": dob,
		"citizenship": citizenship
	}


def validate_south_african_id(id_number):
	"""Boolean-only version of validate_south_african_id_number() - use that
	one instead if you need the gender/DOB/citizenship it also extracts."""
	if not id_number or not id_number.isdigit() or len(id_number) != 13:
		return False

	month = int(id_number[2:4])
	day = int(id_number[4:6])

	if month < 1 or month > 12 or day < 1 or day > 31:
		return False

	checksum = 0
	for i, digit in enumerate(id_number[:-1]):
		num = int(digit)
		if i % 2 == 0:
			checksum += num
		else:
			checksum += (num * 2 if num * 2 <= 9 else num * 2 - 9)

	check_digit = (10 - (checksum % 10)) % 10
	return check_digit == int(id_number[-1])


def get_tax_year_dates(date_in_year=None):
	"""SA tax year runs 1 March to 28/29 February."""
	if not date_in_year:
		date_in_year = date.today()
	else:
		date_in_year = getdate(date_in_year)

	year = date_in_year.year

	if date_in_year.month < 3:
		start_date = date(year - 1, 3, 1)
		end_date = date(year, 2, 29 if calendar.isleap(year) else 28)
	else:
		start_date = date(year, 3, 1)
		next_year = year + 1
		end_date = date(next_year, 2, 29 if calendar.isleap(next_year) else 28)

	return (start_date, end_date)
