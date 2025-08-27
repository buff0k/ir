# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.xlsxutils import make_xlsx

# Column keys follow the prescribed layout:
# Occupational Levels | Male A C I W | Female A C I W | Foreign Nationals Male Female | Total

MALE_KEYS   = ["a_male", "c_male", "i_male", "w_male"]
FEMALE_KEYS = ["a_female", "c_female", "i_female", "w_female"]

DG_MAP = {  # designated group -> column key base
    "African":  "a",
    "Coloured": "c",
    "Indian":   "i",
    "White":    "w",
}

def execute(filters=None):
    if not filters or not filters.get("company") or not filters.get("country"):
        frappe.throw("Please select both Company and Country")

    company      = filters["company"]
    rsa_country  = filters["country"]
    disabled_only = 1 if frappe.utils.cint(filters.get("disabled")) else 0

    # ORDER BY Paterson Band descending (F to A)
    occupational_levels = frappe.get_all(
        "Occupational Level",
        fields=["name", "paterson_band"],
        order_by="FIELD(paterson_band, 'F','E','D','C','B','A')"
    )

    columns = [
        {"fieldname": "occupational_level", "label": "Occupational Levels", "fieldtype": "Data", "width": 320},
        # Male A C I W
        {"fieldname": "a_male", "label": "Male A", "fieldtype": "Int", "width": 60},
        {"fieldname": "c_male", "label": "Male C", "fieldtype": "Int", "width": 60},
        {"fieldname": "i_male", "label": "Male I", "fieldtype": "Int", "width": 60},
        {"fieldname": "w_male", "label": "Male W", "fieldtype": "Int", "width": 60},
        # Female A C I W
        {"fieldname": "a_female", "label": "Female A", "fieldtype": "Int", "width": 70},
        {"fieldname": "c_female", "label": "Female C", "fieldtype": "Int", "width": 70},
        {"fieldname": "i_female", "label": "Female I", "fieldtype": "Int", "width": 70},
        {"fieldname": "w_female", "label": "Female W", "fieldtype": "Int", "width": 70},
        # Foreign + Total
        {"fieldname": "foreign_male",   "label": "Foreign Male",   "fieldtype": "Int", "width": 90},
        {"fieldname": "foreign_female", "label": "Foreign Female", "fieldtype": "Int", "width": 100},
        {"fieldname": "total",          "label": "Total",          "fieldtype": "Int", "width": 70},
    ]

    def base_filters():
        f = {
            "company": company,
            "status": "Active",
        }
        if disabled_only:
            f["custom_disabled_employee"] = 1
        return f

    def count_designated(ol_name, gender, dg, employment_type=None):
        f = base_filters()
        f.update({
            "custom_occupational_level": ol_name,
            "gender": gender,
            "custom_nationality": rsa_country,
            "custom_designated_group": dg,
        })
        if employment_type:
            f["employment_type"] = employment_type
        return frappe.db.count("Employee", f)

    def count_foreign(ol_name, gender, employment_type=None):
        f = base_filters()
        f.update({
            "custom_occupational_level": ol_name,
            "gender": gender,
            "custom_nationality": ["!=", rsa_country],
        })
        if employment_type:
            f["employment_type"] = employment_type
        return frappe.db.count("Employee", f)

    data = []

    # -------- PERMANENT by OCCUPATIONAL LEVEL (exclude Contract)
    permanent_totals_accumulator = init_zero_row("TOTAL PERMANENT")
    for ol in occupational_levels:
        row = init_zero_row(ol.name)

        # designated groups (RSA nationals only)
        for dg, colbase in DG_MAP.items():
            # male/female
            m = count_designated(ol.name, "Male", dg, employment_type=None) - count_designated(ol.name, "Male", dg, employment_type="Contract")
            f = count_designated(ol.name, "Female", dg, employment_type=None) - count_designated(ol.name, "Female", dg, employment_type="Contract")
            row[f"{colbase}_male"]   += m
            row[f"{colbase}_female"] += f

        # foreign nationals (no designated group split)
        fm = count_foreign(ol.name, "Male", employment_type=None) - count_foreign(ol.name, "Male", employment_type="Contract")
        ff = count_foreign(ol.name, "Female", employment_type=None) - count_foreign(ol.name, "Female", employment_type="Contract")
        row["foreign_male"] += fm
        row["foreign_female"] += ff

        row["total"] = row_sum(row)

        # accumulate for TOTAL PERMANENT
        add_into(permanent_totals_accumulator, row)

        data.append(row)

    # TOTAL PERMANENT row
    permanent_totals_accumulator["occupational_level"] = "TOTAL PERMANENT"
    permanent_totals_accumulator["is_total_row"] = 1
    permanent_totals_accumulator["total"] = row_sum(permanent_totals_accumulator)
    data.append(permanent_totals_accumulator)

    # -------- TEMPORARY EMPLOYEES (Contract) as single row
    temp_row = init_zero_row("Temporary employees")
    for dg, colbase in DG_MAP.items():
        temp_row[f"{colbase}_male"]   = sum(count_designated(ol.name, "Male", dg, "Contract") for ol in occupational_levels)
        temp_row[f"{colbase}_female"] = sum(count_designated(ol.name, "Female", dg, "Contract") for ol in occupational_levels)
    temp_row["foreign_male"]   = sum(count_foreign(ol.name, "Male", "Contract") for ol in occupational_levels)
    temp_row["foreign_female"] = sum(count_foreign(ol.name, "Female", "Contract") for ol in occupational_levels)
    temp_row["total"] = row_sum(temp_row)
    data.append(temp_row)

    # -------- GRAND TOTAL = TOTAL PERMANENT + TEMPORARY
    grand = init_zero_row("GRAND TOTAL")
    add_into(grand, permanent_totals_accumulator)
    add_into(grand, temp_row)
    grand["is_total_row"] = 1
    grand["total"] = row_sum(grand)
    data.append(grand)

    return columns, data


def init_zero_row(label):
    row = {"occupational_level": label}
    for k in MALE_KEYS + FEMALE_KEYS:
        row[k] = 0
    row["foreign_male"] = 0
    row["foreign_female"] = 0
    row["total"] = 0
    return row


def add_into(acc, row):
    for k in MALE_KEYS + FEMALE_KEYS + ["foreign_male", "foreign_female"]:
        acc[k] = acc.get(k, 0) + row.get(k, 0)


def row_sum(row):
    return sum(row.get(k, 0) for k in MALE_KEYS + FEMALE_KEYS + ["foreign_male", "foreign_female"])


@frappe.whitelist()
def download_eea2_xlsx(company, country, disabled=0):
    # reuse execute with filters including disabled
    columns, data = execute({"company": company, "country": country, "disabled": frappe.utils.cint(disabled)})

    xlsx_data = []
    headers = [col["label"] for col in columns]
    xlsx_data.append(headers)

    for row in data:
        xlsx_data.append([row.get(col["fieldname"], "") for col in columns])

    xlsx_file = make_xlsx(xlsx_data, "EEA2_Report")

    frappe.response["type"] = "binary"
    frappe.response["filename"] = "EEA2_Employment_Equity_Report.xlsx"
    frappe.response["filecontent"] = xlsx_file.getvalue()
    frappe.response["content_type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
