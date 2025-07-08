# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters or not filters.get("company") or not filters.get("country"):
        frappe.throw("Please select both Company and Country")

    company = filters["company"]
    rsa_country = filters["country"]

    # Order groups as standard
    designated_groups = ["African", "Coloured", "Indian", "White"]
    genders = ["Male", "Female"]

    occupational_levels = [r.name for r in frappe.get_all("Occupational Level", order_by="name")]

    # Build dynamic columns: e.g. African Male, African Female ...
    columns = [
        {"fieldname": "occupational_level", "label": "Occupational Level", "fieldtype": "Data", "width": 200}
    ]

    group_columns = []
    for dg in designated_groups:
        for gender in genders:
            col_name = f"{dg.lower()}_{gender.lower()}"
            columns.append({
                "fieldname": col_name,
                "label": f"{dg} {gender}",
                "fieldtype": "Int",
                "width": 80
            })
            group_columns.append(col_name)

    # Add Foreign Nationals
    for gender in genders:
        col_name = f"foreign_{gender.lower()}"
        columns.append({
            "fieldname": col_name,
            "label": f"Foreign {gender}",
            "fieldtype": "Int",
            "width": 80
        })
        group_columns.append(col_name)

    # Add Total
    columns.append({
        "fieldname": "total",
        "label": "Total",
        "fieldtype": "Int",
        "width": 100
    })

    data = []

    for ol in occupational_levels:
        row = {"occupational_level": ol}
        row_total = 0

        # Local counts
        for dg in designated_groups:
            for gender in genders:
                count = frappe.db.count("Employee", {
                    "company": company,
                    "custom_occupational_level": ol,
                    "custom_designated_group": dg,
                    "gender": gender,
                    "custom_nationality": rsa_country,
                    "status": "Active"
                })
                key = f"{dg.lower()}_{gender.lower()}"
                row[key] = count
                row_total += count

        # Foreign counts
        for gender in genders:
            foreign_count = frappe.db.count("Employee", {
                "company": company,
                "custom_occupational_level": ol,
                "gender": gender,
                "status": "Active",
                "custom_nationality": ["!=", rsa_country]
            })
            row[f"foreign_{gender.lower()}"] = foreign_count
            row_total += foreign_count

        row["total"] = row_total
        data.append(row)

    return columns, data
