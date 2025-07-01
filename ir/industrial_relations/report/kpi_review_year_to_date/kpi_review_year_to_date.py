# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    conditions = []
    values = {}

    if filters.get("year"):
        conditions.append("YEAR(date_of_review) = %(year)s")
        values["year"] = filters.get("year")

    if filters.get("site"):
        conditions.append("branch = %(site)s")
        values["site"] = filters.get("site")

    if filters.get("kpi_template"):
        conditions.append("kpi_template = %(kpi_template)s")
        values["kpi_template"] = filters.get("kpi_template")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    query = """
        SELECT
            branch AS site,
            kpi_template,
            COUNT(name) AS total_reviews,
            ROUND(AVG(CAST(SUBSTRING_INDEX(score, ' ', 1) AS DECIMAL(10,2))), 2) AS avg_score,
            ROUND(AVG(
                CAST(TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1)) AS DECIMAL(10,2))
            ), 2) AS avg_percentage
        FROM `tabKPI Review`
        {where}
        GROUP BY branch, kpi_template
        ORDER BY branch, kpi_template
    """.format(where=where)

    frappe.log_error(f"QUERY DEBUG\nQUERY:\n{query}\nVALUES:\n{values}", "KPI DEBUG")

    data = frappe.db.sql(query, values, as_dict=True)

    columns = [
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 120},
        {"label": _("KPI Template"), "fieldname": "kpi_template", "fieldtype": "Link", "options": "KPI Template", "width": 200},
        {"label": _("Total Reviews"), "fieldname": "total_reviews", "fieldtype": "Int", "width": 100},
        {"label": _("Average Score"), "fieldname": "avg_score", "fieldtype": "Float", "precision": 2, "width": 100},
        {"label": _("Average %"), "fieldname": "avg_percentage", "fieldtype": "Percent", "precision": 2, "width": 100}
    ]

    return columns, data
