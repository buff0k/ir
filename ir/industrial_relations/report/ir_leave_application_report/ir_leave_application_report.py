# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import csv
import json
from io import StringIO

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
            "label": _("Leave Application"),
            "fieldname": "leave_application",
            "fieldtype": "Link",
            "options": "Leave Application",
            "width": 170,
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 140,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 160,
        },
        {
            "label": _("Branch"),
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 160,
        },
        {
            "label": _("Leave Type"),
            "fieldname": "leave_type",
            "fieldtype": "Link",
            "options": "Leave Type",
            "width": 160,
        },
        {
            "label": _("From Date"),
            "fieldname": "from_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("To Date"),
            "fieldname": "to_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Working Days Leave"),
            "fieldname": "ir_working_days_leave",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "label": _("Total Leave Hours"),
            "fieldname": "ir_total_leave_hours",
            "fieldtype": "Float",
            "width": 140,
        },
        {
            "label": _("Leave as per Payroll"),
            "fieldname": "ir_leave_as_per_payroll",
            "fieldtype": "Float",
            "width": 160,
        },
    ]


def get_data(filters):
    conditions = ["la.docstatus < 2"]
    values = {}

    if filters.get("company"):
        conditions.append("la.company = %(company)s")
        values["company"] = filters.company

    if filters.get("from_date"):
        conditions.append("la.to_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("la.from_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("application_status"):
        conditions.append("la.status = %(application_status)s")
        values["application_status"] = filters.application_status

    if filters.get("branch"):
        conditions.append("emp.branch = %(branch)s")
        values["branch"] = filters.branch

    if filters.get("leave_type"):
        conditions.append("la.leave_type = %(leave_type)s")
        values["leave_type"] = filters.leave_type

    query = f"""
        SELECT
            la.name AS leave_application,
            la.employee,
            la.employee_name,
            la.company,
            emp.branch,
            la.leave_type,
            la.from_date,
            la.to_date,
            la.ir_working_days_leave,
            la.ir_total_leave_hours,
            la.ir_leave_as_per_payroll
        FROM
            `tabLeave Application` la
        LEFT JOIN
            `tabEmployee` emp
            ON emp.name = la.employee
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            la.from_date DESC,
            la.employee_name ASC
    """

    return frappe.db.sql(query, values, as_dict=True)


@frappe.whitelist()
def export_vip_leave_file(filters=None):
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = frappe._dict(filters or {})
    rows = get_data(filters)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "Leave Application",
            "Employee",
            "Employee Name",
            "Company",
            "Branch",
            "Leave Type",
            "From Date",
            "To Date",
            "Working Days Leave",
            "Total Leave Hours",
            "Leave as per Payroll",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.leave_application or "",
                row.employee or "",
                row.employee_name or "",
                row.company or "",
                row.branch or "",
                row.leave_type or "",
                row.from_date or "",
                row.to_date or "",
                row.ir_working_days_leave or 0,
                row.ir_total_leave_hours or 0,
                row.ir_leave_as_per_payroll or 0,
            ]
        )

    return {
        "filename": "vip_leave_export.csv",
        "content": output.getvalue(),
    }