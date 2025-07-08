# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.xlsxutils import make_xlsx
from frappe.utils.response import build_response

def execute(filters=None):
    if not filters or not filters.get("company") or not filters.get("country"):
        frappe.throw("Please select both Company and Country")

    company = filters["company"]
    rsa_country = filters["country"]

    designated_groups = ["African", "Coloured", "Indian", "White"]
    genders = ["Male", "Female"]

    # ORDER BY Paterson Band descending (F to A)
    occupational_levels = frappe.get_all(
        "Occupational Level",
        fields=["name", "paterson_band"],
        order_by="FIELD(paterson_band, 'F','E','D','C','B','A')"
    )

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

    ### -----------------------------
    ### 1️⃣ WORKFORCE PROFILE (ALL)
    ### -----------------------------
    for ol in occupational_levels:
        row = {"section": "Workforce Profile", "occupational_level": ol.name}
        row_total = 0

        for dg in designated_groups:
            for gender in genders:
                count = frappe.db.count("Employee", {
                    "company": company,
                    "custom_occupational_level": ol.name,
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
                "custom_occupational_level": ol.name,
                "gender": gender,
                "status": "Active",
                "custom_nationality": ["!=", rsa_country]
            })
            row[f"foreign_{gender.lower()}"] = foreign
            row_total += foreign

        row["total"] = row_total
        data.append(row)

    # TEMPORARY row (subset only)
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

    ### -----------------------------
    ### 2️⃣ DISABLED PROFILE (ONLY)
    ### -----------------------------
    for ol in occupational_levels:
        row = {"section": "Disabled Profile", "occupational_level": ol.name}
        row_total = 0

        for dg in designated_groups:
            for gender in genders:
                count = frappe.db.count("Employee", {
                    "company": company,
                    "custom_occupational_level": ol.name,
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
                "custom_occupational_level": ol.name,
                "gender": gender,
                "status": "Active",
                "custom_nationality": ["!=", rsa_country],
                "custom_disabled_employee": 1
            })
            row[f"foreign_{gender.lower()}"] = foreign
            row_total += foreign

        row["total"] = row_total
        data.append(row)

    # DISABLED TEMPORARY
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
                "employment_type": "Contract",
                "custom_disabled_employee": 1
            })
            row[f"{dg.lower()}_{gender.lower()}"] = count
            row_total += count

    for gender in genders:
        foreign = frappe.db.count("Employee", {
            "company": company,
            "gender": gender,
            "status": "Active",
            "custom_nationality": ["!=", rsa_country],
            "employment_type": "Contract",
            "custom_disabled_employee": 1
        })
        row[f"foreign_{gender.lower()}"] = foreign
        row_total += foreign

    row["total"] = row_total
    data.append(row)

    return columns, data

@frappe.whitelist()
def download_eea2_xlsx(company, country):
    from ir.industrial_relations.report.employment_equity_report.employment_equity_report import execute

    filters = {"company": company, "country": country}
    columns, data = execute(filters)

    xlsx_data = []
    headers = [col["label"] for col in columns]
    xlsx_data.append(headers)

    for row in data:
        row_list = [row.get(col["fieldname"], "") for col in columns]
        xlsx_data.append(row_list)

    xlsx_file = make_xlsx(xlsx_data, "EEA2_Report")

    frappe.response['type'] = 'binary'
    frappe.response['filename'] = 'EEA2_Employment_Equity_Report.xlsx'
    frappe.response['filecontent'] = xlsx_file.getvalue()
    frappe.response['content_type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

