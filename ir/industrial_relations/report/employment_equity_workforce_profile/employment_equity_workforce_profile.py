# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _


OCCUPATIONAL_LEVELS = [
    "Top management",
    "Senior management",
    "Professionally qualified",
    "Skilled technical",
    "Semi-skilled",
    "Unskilled",
]

RACE_GENDER_COLUMNS = [
    ("Male", "African", "male_african"),
    ("Male", "Coloured", "male_coloured"),
    ("Male", "Indian", "male_indian"),
    ("Male", "White", "male_white"),
    ("Female", "African", "female_african"),
    ("Female", "Coloured", "female_coloured"),
    ("Female", "Indian", "female_indian"),
    ("Female", "White", "female_white"),
]

EMPLOYMENT_CATEGORIES = ["Permanent", "Temporary"]


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns(filters)
    employees = get_employees(filters)
    data = build_data(employees, filters)
    chart = get_chart(data)
    summary = get_report_summary(data)

    return columns, data, None, chart, summary


def get_columns(filters):
    columns = [
        {
            "label": _("Occupational Level"),
            "fieldname": "occupational_level",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Employment Category"),
            "fieldname": "employment_category",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Male African"),
            "fieldname": "male_african",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Male Coloured"),
            "fieldname": "male_coloured",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Male Indian"),
            "fieldname": "male_indian",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Male White"),
            "fieldname": "male_white",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Female African"),
            "fieldname": "female_african",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Female Coloured"),
            "fieldname": "female_coloured",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": _("Female Indian"),
            "fieldname": "female_indian",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Female White"),
            "fieldname": "female_white",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Foreign Male"),
            "fieldname": "foreign_male",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Foreign Female"),
            "fieldname": "foreign_female",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Disabled Male"),
            "fieldname": "disabled_male",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Disabled Female"),
            "fieldname": "disabled_female",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Total Employees"),
            "fieldname": "total_employees",
            "fieldtype": "Int",
            "width": 120,
        },
    ]

    if filters.get("show_detailed_rows"):
        columns.extend([
            {
                "label": _("SA Total"),
                "fieldname": "sa_total",
                "fieldtype": "Int",
                "width": 100,
            },
            {
                "label": _("Foreign Total"),
                "fieldname": "foreign_total",
                "fieldtype": "Int",
                "width": 110,
            },
            {
                "label": _("Disabled Total"),
                "fieldname": "disabled_total",
                "fieldtype": "Int",
                "width": 110,
            },
            {
                "label": _("Branch"),
                "fieldname": "branch",
                "fieldtype": "Data",
                "width": 140,
            },
        ])

    return columns


def get_employees(filters):
    conditions = [
        "company = %(company)s",
        "date_of_joining <= %(as_at_date)s",
        "status != 'Inactive'",
    ]

    if filters.get("include_suspended"):
        conditions.append("status in ('Active', 'Suspended')")
    else:
        conditions.append("status = 'Active'")

    if filters.get("branch"):
        conditions.append("branch = %(branch)s")

    if filters.get("occupational_level"):
        conditions.append("custom_occupational_level = %(occupational_level)s")

    employment_category = filters.get("employment_category")
    if employment_category == "Permanent":
        conditions.append("employment_type = 'Full-time'")
    elif employment_category == "Temporary":
        conditions.append("employment_type = 'Contract'")

    return frappe.db.sql(
        f"""
        SELECT
            name,
            company,
            branch,
            employment_type,
            custom_occupational_level,
            gender,
            za_nationality,
            za_race,
            za_is_disabled,
            status,
            date_of_joining,
            relieving_date
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY custom_occupational_level, employment_type, branch, name
        """,
        filters,
        as_dict=True,
    )


def build_data(employees, filters):
    rows = []

    for level in OCCUPATIONAL_LEVELS:
        for employment_category in EMPLOYMENT_CATEGORIES:
            row = make_empty_row(level, employment_category, filters.get("branch"))

            matching_employees = [
                emp
                for emp in employees
                if emp.custom_occupational_level == level
                and map_employment_category(emp.employment_type) == employment_category
            ]

            for emp in matching_employees:
                apply_employee_to_row(row, emp)

            if row["total_employees"] > 0:
                rows.append(row)

    total_row = get_total_row(rows, filters)

    if total_row["total_employees"] > 0:
        rows.append({})
        rows.append(total_row)

    return rows


def make_empty_row(level, employment_category, branch=None):
    return {
        "occupational_level": level,
        "employment_category": employment_category,
        "branch": branch or "",
        "male_african": 0,
        "male_coloured": 0,
        "male_indian": 0,
        "male_white": 0,
        "female_african": 0,
        "female_coloured": 0,
        "female_indian": 0,
        "female_white": 0,
        "foreign_male": 0,
        "foreign_female": 0,
        "disabled_male": 0,
        "disabled_female": 0,
        "sa_total": 0,
        "foreign_total": 0,
        "disabled_total": 0,
        "total_employees": 0,
    }


def apply_employee_to_row(row, employee):
    gender = clean_value(employee.gender)
    nationality = clean_value(employee.za_nationality)
    race = clean_value(employee.za_race)

    is_foreign = nationality and nationality != "South Africa"
    is_disabled = cint_safe(employee.za_is_disabled)

    if is_foreign:
        if gender == "Male":
            row["foreign_male"] += 1
        elif gender == "Female":
            row["foreign_female"] += 1
        row["foreign_total"] += 1
    else:
        matched = False
        for col_gender, col_race, col_field in RACE_GENDER_COLUMNS:
            if gender == col_gender and race == col_race:
                row[col_field] += 1
                matched = True
                break

        if matched:
            row["sa_total"] += 1

    if is_disabled:
        if gender == "Male":
            row["disabled_male"] += 1
        elif gender == "Female":
            row["disabled_female"] += 1
        row["disabled_total"] += 1

    row["total_employees"] += 1


def get_total_row(rows, filters):
    total_row = make_empty_row("TOTAL", "", filters.get("branch"))

    summable_fields = [
        "male_african",
        "male_coloured",
        "male_indian",
        "male_white",
        "female_african",
        "female_coloured",
        "female_indian",
        "female_white",
        "foreign_male",
        "foreign_female",
        "disabled_male",
        "disabled_female",
        "sa_total",
        "foreign_total",
        "disabled_total",
        "total_employees",
    ]

    for row in rows:
        if not row:
            continue

        for field in summable_fields:
            total_row[field] += row.get(field, 0)

    return total_row


def map_employment_category(employment_type):
    employment_type = clean_value(employment_type)

    if employment_type == "Full-time":
        return "Permanent"
    if employment_type == "Contract":
        return "Temporary"

    return "Other"


def clean_value(value):
    return (value or "").strip()


def cint_safe(value):
    return 1 if value else 0


def get_chart(data):
    chart_rows = [
        row
        for row in data
        if row
        and row.get("occupational_level")
        and row.get("occupational_level") != "TOTAL"
    ]

    labels = [
        f"{row['occupational_level']} ({row['employment_category']})"
        for row in chart_rows
    ]
    values = [row["total_employees"] for row in chart_rows]

    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Employees"),
                    "values": values,
                }
            ],
        },
        "type": "bar",
        "height": 320,
    }


def get_report_summary(data):
    actual_rows = [
        row
        for row in data
        if row and row.get("occupational_level") not in ("TOTAL", "")
    ]

    total_employees = sum(row.get("total_employees", 0) for row in actual_rows)
    total_disabled = sum(row.get("disabled_total", 0) for row in actual_rows)
    total_foreign = sum(row.get("foreign_total", 0) for row in actual_rows)
    total_sa = sum(row.get("sa_total", 0) for row in actual_rows)

    return [
        {
            "value": total_employees,
            "label": _("Total Employees"),
            "datatype": "Int",
        },
        {
            "value": total_sa,
            "label": _("South African Employees"),
            "datatype": "Int",
        },
        {
            "value": total_foreign,
            "label": _("Foreign Nationals"),
            "datatype": "Int",
        },
        {
            "value": total_disabled,
            "label": _("Employees with Disabilities"),
            "datatype": "Int",
        },
    ]