# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{
			"label": _("Disciplinary Action"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Disciplinary Action",
			"width": 160,
		},
		{
			"label": _("Request Date"),
			"fieldname": "request_date",
			"fieldtype": "Datetime",
			"width": 150,
		},
		{
			"label": _("Outcome Date"),
			"fieldname": "outcome_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Days to Complete"),
			"fieldname": "days_to_complete",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 180,
		},
		{
			"label": _("Branch"),
			"fieldname": "branch",
			"fieldtype": "Link",
			"options": "Branch",
			"width": 180,
		},
		{
			"label": _("Accused"),
			"fieldname": "accused_display",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Outcome"),
			"fieldname": "display_outcome",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Responsible IR"),
			"fieldname": "responsible_ir_display",
			"fieldtype": "Data",
			"width": 220,
		},
	]


def get_data(filters):
	conditions = ["da.docstatus < 2"]
	values = {}

	if filters.get("company"):
		conditions.append("da.company = %(company)s")
		values["company"] = filters.company

	if filters.get("branch"):
		conditions.append("da.branch = %(branch)s")
		values["branch"] = filters.branch

	if filters.get("from_date"):
		conditions.append("DATE(da.request_date) >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("DATE(da.request_date) <= %(to_date)s")
		values["to_date"] = filters.to_date

	if filters.get("outcome"):
		conditions.append("da.outcome = %(outcome)s")
		values["outcome"] = filters.outcome

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			da.name,
			da.request_date,
			da.outcome_date,
			CASE
				WHEN da.outcome_date IS NOT NULL
				THEN DATEDIFF(da.outcome_date, DATE(da.request_date))
				ELSE NULL
			END AS days_to_complete,
			da.company,
			da.branch,
			CASE
				WHEN IFNULL(da.accused_coy, '') != ''
				THEN CONCAT(IFNULL(da.accused_name, ''), ' (', da.accused_coy, ')')
				ELSE IFNULL(da.accused_name, '')
			END AS accused_display,
			CASE
				WHEN IFNULL(oo.disc_offence_out, '') = '' THEN 'Pending'
				ELSE oo.disc_offence_out
			END AS display_outcome,
			CASE
				WHEN IFNULL(da.responsible_ir_no, '') != ''
				THEN CONCAT(IFNULL(da.responsible_ir_name, ''), ' (', da.responsible_ir_no, ')')
				ELSE IFNULL(da.responsible_ir_name, '')
			END AS responsible_ir_display
		FROM `tabDisciplinary Action` da
		LEFT JOIN `tabOffence Outcome` oo
			ON oo.name = da.outcome
		WHERE {where_clause}
		ORDER BY da.request_date DESC, da.name DESC
		""",
		values,
		as_dict=True,
	)