# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters or not filters.get("company"):
        frappe.throw("Company is required")

    conditions = ["e.company = %(company)s"]
    if filters.get("trade_union"):
        conditions.append("e.custom_trade_union = %(trade_union)s")
    if filters.get("branch"):
        conditions.append("e.branch = %(branch)s")

    condition_str = " AND ".join(conditions)

    return get_columns(), frappe.db.sql(f"""
        SELECT
            e.name AS employee,
            e.employee_name,
            e.branch,
            e.custom_trade_union,
            e.custom_trade_union_membership_start,
            CASE
                WHEN ss.ss_id IS NOT NULL THEN 'Yes'
                ELSE 'No'
            END AS shop_steward
        FROM `tabEmployee` e
        LEFT JOIN `tabTrade Union` tu ON tu.name = e.custom_trade_union
        LEFT JOIN `tabUnion Shop Stewards` ss ON ss.parent = tu.name AND ss.ss_id = e.name
        WHERE {condition_str}
    """, filters, as_dict=0)
    

def get_columns():
    return [
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 150},
        {"label": "Branch", "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
        {"label": "Trade Union", "fieldname": "custom_trade_union", "fieldtype": "Link", "options": "Trade Union", "width": 150},
        {"label": "Membership Start", "fieldname": "custom_trade_union_membership_start", "fieldtype": "Date", "width": 120},
        {"label": "Shop Steward", "fieldname": "shop_steward", "fieldtype": "Data", "width": 100},
    ]
