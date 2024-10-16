# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_months, today

def execute(filters=None):
    if not filters:
        filters = {}
    
    # Get current date and calculate future date based on X months filter
    current_date = today()
    future_date = add_months(current_date, filters.get("months") or 0)
    
    # Query to get contracts expiring within the next X months
    data = frappe.db.sql("""
        SELECT
            name AS document_name,
            company,
            employee,
            employee_name,
            designation,
            date_of_joining,
            branch,
            project,
            start_date,
            end_date
        FROM
            `tabContract of Employment`
        WHERE
            has_expiry = 1
            AND end_date BETWEEN %s AND %s
    """, (current_date, future_date), as_dict=True)

    columns = [
        {"label": "Contract", "fieldname": "document_name", "fieldtype": "Link", "options": "Contract of Employment", "width": 50},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 50},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 50},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
        {"label": "Designation", "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 150},
        {"label": "Employee Start Date", "fieldname": "date_of_joining", "fieldtype": "Date", "width": 150},
        {"label": "Branch", "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 100},
        {"label": "Project", "fieldname": "project", "fieldtype": "Data", "width": 150},
        {"label": "Contract Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 150},
        {"label": "Contract End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 150},
    ]

    return columns, data
