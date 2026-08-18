# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class IRPayrollCostSettings(Document):
	pass


def get_basic_wage_components():
	"""The Salary Components explicitly designated here as Basic/Wages (e.g.
	Basic, Basic Salary, Hourly Earnings). Site Budget's cost breakdown
	treats every other Earning-type Salary Structure row as an Allowance by
	default, so only Basic/Wages needs curating here - see
	compute_salary_structure_totals() in site_budget_map.py."""
	settings = frappe.get_cached_doc("IR Payroll Cost Settings")
	return {row.salary_component for row in settings.basic_wage_components or [] if row.salary_component}
