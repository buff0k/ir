# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from ir.industrial_relations.doctype.site_organogram.branch_staffing import (
	get_current_snapshot,
	get_trend_data,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = get_columns()
	data = get_data(filters)
	chart = get_trend_data(
		company=filters.get("company"),
		branches=filters.get("branches"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
	)

	return columns, data, None, chart


def get_columns():
	return [
		{
			"label": _("Branch"),
			"fieldname": "branch",
			"fieldtype": "Link",
			"options": "Branch",
			"width": 200,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Total Roles"),
			"fieldname": "total",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Filled"),
			"fieldname": "filled",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Vacant"),
			"fieldname": "vacant",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Fill %"),
			"fieldname": "fill_percent",
			"fieldtype": "Percent",
			"width": 100,
		},
	]


def get_data(filters):
	rows = get_current_snapshot(
		company=filters.get("company"),
		branches=filters.get("branches"),
	)

	for row in rows:
		row["fill_percent"] = round((row["filled"] / row["total"]) * 100, 1) if row["total"] else 0

	rows.sort(key=lambda r: (r["branch"], r["designation"]))

	return rows
