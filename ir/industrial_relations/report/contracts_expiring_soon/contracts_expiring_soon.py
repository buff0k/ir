# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today, add_days, getdate
from datetime import timedelta

def execute(filters=None):
    threshold_date = getdate(today()) + timedelta(weeks=4)

    # Fetch contracts expiring soon
    expiring_contracts = frappe.db.sql("""
        SELECT
            co.name AS contract_name,
            co.employee,
            co.employee_name,
            co.end_date,
            co.creation
        FROM
            `tabContract of Employment` co
        WHERE
            co.end_date <= %(threshold_date)s
            AND co.end_date IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM `tabContract of Employment` co2
                WHERE co2.employee = co.employee
                AND co2.creation > co.creation
            )
    """, {"threshold_date": threshold_date}, as_dict=True)

    columns = [
        {"label": "Contract Name", "fieldname": "contract_name", "fieldtype": "Link", "options": "Contract of Employment"},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee"},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data"},
        {"label": "Expiry Date", "fieldname": "end_date", "fieldtype": "Date"},
        {"label": "Creation Date", "fieldname": "creation", "fieldtype": "Datetime"},
    ]
    return columns, expiring_contracts
