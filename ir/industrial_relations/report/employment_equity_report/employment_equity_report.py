# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters or not filters.get("company"):
        frappe.throw("Please select a Company")

    company = filters["company"]

    # Fetch all occupational levels
    occupational_levels = [r.name for r in frappe.get_all("Occupational Level", order_by="name")]

    # Fetch all designated groups
    designated_groups = [r.name for r in frappe.get_all("Designated Group", order_by="name")]

    columns = [
        {"fieldname": "occupational_level", "label": "Occupational Level", "fieldtype": "Data", "width": 200},
        {"fieldname": "designated_group", "label": "Designated Group", "fieldtype": "Data", "width": 180},
        {"fieldname": "male", "label": "Male", "fieldtype": "Int", "width": 80},
        {"fieldname": "female", "label": "Female", "fieldtype": "Int", "width": 80},
        {"fieldname": "total", "label": "Total", "fieldtype": "Int", "width": 80},
    ]

    data = []

    for ol in occupational_levels:
        for dg in designated_groups:
            male_count = frappe.db.count("Employee", {
                "company": company,
                "custom_occupational_level": ol,
                "custom_designated_group": dg,
                "gender": "Male",
                "status": "Active"
            })
            female_count = frappe.db.count("Employee", {
                "company": company,
                "custom_occupational_level": ol,
                "custom_designated_group": dg,
                "gender": "Female",
                "status": "Active"
            })

            row_total = male_count + female_count

            data.append({
                "occupational_level": ol,
                "designated_group": dg,
                "male": male_count,
                "female": female_count,
                "total": row_total
            })

    return columns, data
