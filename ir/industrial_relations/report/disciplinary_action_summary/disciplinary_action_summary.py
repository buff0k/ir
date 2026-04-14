# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_days

def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(filters)

	return columns, data, None, chart

def get_columns():
	return [
		{
			"label": _("Disciplinary Action"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Disciplinary Action",
			"width": 170,
		},
		{
			"label": _("Request Date"),
			"fieldname": "request_date",
			"fieldtype": "Date",
			"width": 110,
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
			"label": _("Final Charges"),
			"fieldname": "final_charges_display",
			"fieldtype": "Small Text",
			"width": 360,
		},
		{
			"label": _("Outcome"),
			"fieldname": "display_outcome",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Reason for Cancellation"),
			"fieldname": "reason_for_cancellation",
			"fieldtype": "Small Text",
			"width": 260,
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
		values["company"] = filters.get("company")

	if filters.get("branch"):
		conditions.append("da.branch = %(branch)s")
		values["branch"] = filters.get("branch")

	if filters.get("from_date"):
		conditions.append("DATE(da.request_date) >= %(from_date)s")
		values["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("DATE(da.request_date) <= %(to_date)s")
		values["to_date"] = filters.get("to_date")

	if filters.get("outcome"):
		conditions.append("da.outcome = %(outcome)s")
		values["outcome"] = filters.get("outcome")

	where_clause = " AND ".join(conditions)

	query = f"""
		SELECT
			da.name,
			DATE(da.request_date) AS request_date,
			da.outcome_date,
			CASE
				WHEN da.outcome_date IS NOT NULL
				THEN DATEDIFF(da.outcome_date, DATE(da.request_date))
				ELSE NULL
			END AS days_to_complete,
			da.company,
			da.branch,
			CASE
				WHEN IFNULL(TRIM(da.accused_name), '') != '' AND IFNULL(TRIM(da.accused_coy), '') != ''
				THEN CONCAT(TRIM(da.accused_name), ' (', TRIM(da.accused_coy), ')')
				WHEN IFNULL(TRIM(da.accused_name), '') != ''
				THEN TRIM(da.accused_name)
				WHEN IFNULL(TRIM(da.accused_coy), '') != ''
				THEN CONCAT('(', TRIM(da.accused_coy), ')')
				ELSE ''
			END AS accused_display,
			IFNULL(fc.final_charges_display, '') AS final_charges_display,
			CASE
				WHEN IFNULL(oo.disc_offence_out, '') = '' THEN 'Pending'
				ELSE oo.disc_offence_out
			END AS display_outcome,
			CASE
				WHEN IFNULL(oo.disc_offence_out, '') = 'Cancelled'
				THEN IFNULL(hcf.reason_for_cancellation, '')
				ELSE ''
			END AS reason_for_cancellation,
			CASE
				WHEN IFNULL(TRIM(da.responsible_ir_name), '') != '' AND IFNULL(TRIM(da.responsible_ir_no), '') != ''
				THEN CONCAT(TRIM(da.responsible_ir_name), ' (', TRIM(da.responsible_ir_no), ')')
				WHEN IFNULL(TRIM(da.responsible_ir_name), '') != ''
				THEN TRIM(da.responsible_ir_name)
				WHEN IFNULL(TRIM(da.responsible_ir_no), '') != ''
				THEN CONCAT('(', TRIM(da.responsible_ir_no), ')')
				ELSE ''
			END AS responsible_ir_display
		FROM `tabDisciplinary Action` da
		LEFT JOIN `tabOffence Outcome` oo
			ON oo.name = da.outcome
		LEFT JOIN (
			SELECT
				dc.parent,
				GROUP_CONCAT(
					CASE
						WHEN IFNULL(TRIM(dc.code_item), '') != '' AND IFNULL(TRIM(dc.charge), '') != ''
						THEN CONCAT(TRIM(dc.code_item), ': ', TRIM(dc.charge))
						WHEN IFNULL(TRIM(dc.charge), '') != ''
						THEN TRIM(dc.charge)
						WHEN IFNULL(TRIM(dc.code_item), '') != ''
						THEN TRIM(dc.code_item)
						ELSE NULL
					END
					ORDER BY dc.idx ASC
					SEPARATOR '\\n'
				) AS final_charges_display
			FROM `tabDisciplinary Charges` dc
			WHERE dc.parenttype = 'Disciplinary Action'
			  AND dc.parentfield = 'final_charges'
			GROUP BY dc.parent
		) fc
			ON fc.parent = da.name
		LEFT JOIN (
			SELECT
				hcf.linked_disciplinary_action,
				hcf.reason_for_cancellation
			FROM `tabHearing Cancellation Form` hcf
			INNER JOIN (
				SELECT
					linked_disciplinary_action,
					MAX(creation) AS latest_creation
				FROM `tabHearing Cancellation Form`
				WHERE IFNULL(linked_disciplinary_action, '') != ''
				  AND docstatus = 1
				GROUP BY linked_disciplinary_action
			) latest_hcf
				ON latest_hcf.linked_disciplinary_action = hcf.linked_disciplinary_action
				AND latest_hcf.latest_creation = hcf.creation
			WHERE hcf.docstatus = 1
		) hcf
			ON hcf.linked_disciplinary_action = da.name
		WHERE {where_clause}
		ORDER BY da.request_date DESC, da.name DESC
	"""

	return frappe.db.sql(query, values, as_dict=True)

def get_chart_data(filters):
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None

	if not from_date or not to_date:
		return None

	# Build full date range so missing days still show as 0
	labels = []
	current = from_date
	while current <= to_date:
		labels.append(str(current))
		current = add_days(current, 1)

	conditions_opened = ["da.docstatus < 2", "DATE(da.request_date) BETWEEN %(from_date)s AND %(to_date)s"]
	conditions_closed = ["da.docstatus < 2", "da.outcome_date IS NOT NULL", "da.outcome_date BETWEEN %(from_date)s AND %(to_date)s"]
	values = {
		"from_date": from_date,
		"to_date": to_date,
	}

	if filters.get("company"):
		conditions_opened.append("da.company = %(company)s")
		conditions_closed.append("da.company = %(company)s")
		values["company"] = filters.get("company")

	if filters.get("branch"):
		conditions_opened.append("da.branch = %(branch)s")
		conditions_closed.append("da.branch = %(branch)s")
		values["branch"] = filters.get("branch")

	if filters.get("outcome"):
		conditions_opened.append("da.outcome = %(outcome)s")
		conditions_closed.append("da.outcome = %(outcome)s")
		values["outcome"] = filters.get("outcome")

	opened = frappe.db.sql(
		f"""
		SELECT
			DATE(da.request_date) AS dt,
			COUNT(*) AS total
		FROM `tabDisciplinary Action` da
		WHERE {' AND '.join(conditions_opened)}
		GROUP BY DATE(da.request_date)
		ORDER BY dt
		""",
		values,
		as_dict=True,
	)

	closed = frappe.db.sql(
		f"""
		SELECT
			da.outcome_date AS dt,
			COUNT(*) AS total
		FROM `tabDisciplinary Action` da
		WHERE {' AND '.join(conditions_closed)}
		GROUP BY da.outcome_date
		ORDER BY dt
		""",
		values,
		as_dict=True,
	)

	opened_map = {str(row.dt): row.total for row in opened}
	closed_map = {str(row.dt): row.total for row in closed}

	opened_values = [opened_map.get(label, 0) for label in labels]
	closed_values = [closed_map.get(label, 0) for label in labels]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": "Opened",
					"values": opened_values,
				},
				{
					"name": "Closed",
					"values": closed_values,
				},
			],
		},
		"type": "line",
		"height": 300,
		"colors": ["#ff4d4f", "#52c41a"],
	}