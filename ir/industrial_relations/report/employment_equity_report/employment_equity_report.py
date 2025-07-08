# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters or not filters.get("company") or not filters.get("country"):
        frappe.throw("Please select both Company and Country")

    company = filters["company"]
    rsa_country = filters["country"]

    designated_groups = ["African", "Coloured", "Indian", "White"]
    genders = ["Male", "Female"]

    occupational_levels = [r.name for r in frappe.get_all("Occupational Level", order_by="name")]

    columns = [
        {"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 200},
        {"fieldname": "occupational_level", "label": "Occupational Level", "fieldtype": "Data", "width": 200}
    ]

    for dg in designated_groups:
        for gender in genders:
            col = f"{dg.lower()}_{gender.lower()}"
            columns.append({
                "fieldname": col,
                "label": f"{dg} {gender}",
                "fieldtype": "Int",
                "width": 80
            })

    for gender in genders:
        col = f"foreign_{gender.lower()}"
        columns.append({
            "fieldname": col,
            "label": f"Foreign {gender}",
            "fieldtype": "Int",
            "width": 80
        })

    columns.append({
        "fieldname": "total",
        "label": "Total",
        "fieldtype": "Int",
        "width": 80
    })

    data = []

    ### WORKFORCE PROFILE ###
    for ol in occupational_levels:
        row = {"section": "Workforce Profile", "occupational_level": ol}
        row_total = 0

        for dg in designated_groups:
            for gender in genders:
                count = frappe.db.count("Employee", {
                    "company": company,
                    "custom_occupational_level": ol,
                    "custom_designated_group": dg,
                    "gender": gender,
                    "status": "Active",
                    "custom_nationality": rsa_country
                })
                row[f"{dg.lower()}_{gender.lower()}"] = count
                row_total += count

        for gender in genders:
            foreign = frappe.db.count("Employee", {
                "company": company,
                "custom_occupational_level": ol,
                "gender": gender,
                "status": "Active",
                "custom_nationality": ["!=", rsa_country]
            })
            row[f"foreign_{gender.lower()}"] = foreign
            row_total += foreign

        row["total"] = row_total
        data.append(row)

    ### TEMPORARY EMPLOYEES ###
    row = {"section": "Workforce Profile", "occupational_level": "Temporary Employees"}
    row_total = 0

    for dg in designated_groups:
        for gender in genders:
            count = frappe.db.count("Employee", {
                "company": company,
                "custom_designated_group": dg,
                "gender": gender,
                "status": "Active",
                "custom_nationality": rsa_country,
                "employment_type": "Contract"
            })
            row[f"{dg.lower()}_{gender.lower()}"] = count
            row_total += count

    for gender in genders:
        foreign = frappe.db.count("Employee", {
            "company": company,
            "gender": gender,
            "status": "Active",
            "custom_nationality": ["!=", rsa_country],
            "employment_type": "Contract"
        })
        row[f"foreign_{gender.lower()}"] = foreign
        row_total += foreign

    row["total"] = row_total
    data.append(row)

    ### DISABLED PROFILE ###
    for ol in occupational_levels:
        row = {"section": "Disabled Profile", "occupational_level": ol}
        row_total = 0

        for dg in designated_groups:
            for gender in genders:
                count = frappe.db.count("Employee", {
                    "company": company,
                    "custom_occupational_level": ol,
                    "custom_designated_group": dg,
                    "gender": gender,
                    "status": "Active",
                    "custom_nationality": rsa_country,
                    "custom_disabled_employee": 1
                })
                row[f"{dg.lower()}_{gender.lower()}"] = count
                row_total += count

        for gender in genders:
            foreign = frappe.db.count("Employee", {
                "company": company,
                "custom_occupational_level": ol,
                "gender": gender,
                "status": "Active",
                "custom_nationality": ["!=", rsa_country],
                "custom_disabled_employee": 1
            })
            row[f"foreign_{gender.lower()}"] = foreign
            row_total += foreign

        row["total"] = row_total
        data.append(row)

    ### DISABLED TEMPORARY ###
    row = {"section": "Disabled Profile", "occupational_level": "Temporary Employees"}
    row_total = 0

    for dg in designated_groups:
        for gender in genders:
            count = frappe.db.count("Employee", {
                "company": company,
                "custom_designated_group": dg,
                "gender": gender,
                "status": "Active",
                "custom_nationality": rsa_country,
                "custom_disabled_employee": 1,
                "employment_type": "Contract"
            })
            row[f"{dg.lower()}_{gender.lower()}"] = count
            row_total += count

    for gender in genders:
        foreign = frappe.db.count("Employee", {
            "company": company,
            "gender": gender,
            "status": "Active",
            "custom_nationality": ["!=", rsa_country],
            "custom_disabled_employee": 1,
            "employment_type": "Contract"
        })
        row[f"foreign_{gender.lower()}"] = foreign
        row_total += foreign

    row["total"] = row_total
    data.append(row)

    return columns, data
