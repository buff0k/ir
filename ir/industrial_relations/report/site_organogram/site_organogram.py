# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters or not filters.get("site_organogram"):
        frappe.throw("Please select a Site Organogram to view the report.")

    # Get the child table rows
    data = frappe.get_all(
        "Site Organogram Details",
        filters={"parent": filters["site_organogram"]},
        fields=["asset", "shift", "designation", "employee_name", "employee"]
    )

    columns = [
        {"label": "Plant No.", "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 120},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 100},
        {"label": "Designation", "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 150},
        {"label": "Operator", "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": "Coy. No.", "fieldname": "employee", "fieldtype": "Data", "width": 120}
    ]

    return columns, data
