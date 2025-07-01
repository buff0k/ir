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
        values["year"] = filters["year"]

    if filters.get("site"):
        conditions.append("branch = %(site)s")
        values["site"] = filters["site"]

    if filters.get("kpi_template"):
        conditions.append("kpi_template = %(kpi_template)s")
        values["kpi_template"] = filters["kpi_template"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Group query
    group_query = """
        SELECT 
            branch AS site,
            kpi_template,
            COUNT(name) AS total_reviews,
            SUM(CAST(SUBSTRING_INDEX(score, ' ', 1) AS DECIMAL(10,2))) AS total_score,
            SUM(CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(score, '/', -1), '(', 1) AS DECIMAL(10,2))) AS total_possible,
            ROUND(AVG(CAST(TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1)) AS DECIMAL(10,2))), 2) AS avg_percentage
        FROM `tabKPI Review`
        {where}
        GROUP BY branch, kpi_template
        ORDER BY branch, kpi_template
    """.format(where=where_clause)

    detail_query = """
        SELECT
            branch AS site,
            kpi_template,
            name AS review_name,
            score
        FROM `tabKPI Review`
        {where}
    """.format(where=where_clause)

    groups = frappe.db.sql(group_query, values, as_dict=True)
    details = frappe.db.sql(detail_query, values, as_dict=True)

    data = []

    for g in groups:
        total_score = g.total_score or 0
        total_possible = g.total_possible or 0
        avg_score = f"{round(total_score, 2)}/{round(total_possible, 2)}" if total_possible else "-"

        data.append({
            "site": g.site or "(No Site)",
            "kpi_template": g.kpi_template,
            "total_reviews": g.total_reviews,
            "avg_score": avg_score,
            "avg_percentage": round(g.avg_percentage or 0, 2),
            "review_link": "",
            "is_group": 1
        })

        for d in details:
            if d.site == g.site and d.kpi_template == g.kpi_template:
                score_display = "-"
                if d.score:
                    parts = d.score.split("/")
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].split("(")[0].strip()
                        score_display = f"{left}/{right}"
                    else:
                        score_display = d.score

                # ✅ Always fallback to "(No Site)" if None
                site_label = d.site or "(No Site)"

                data.append({
                    "site": f"↳ {site_label}",
                    "kpi_template": "",
                    "total_reviews": "",
                    "avg_score": score_display,
                    "avg_percentage": "",
                    "review_link": d.review_name,
                    "is_group": 0
                })

    columns = [
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 120},
        {"label": _("KPI Template"), "fieldname": "kpi_template", "fieldtype": "Link", "options": "KPI Template", "width": 200},
        {"label": _("Total Reviews"), "fieldname": "total_reviews", "fieldtype": "Int", "width": 100},
        {"label": _("Average Score"), "fieldname": "avg_score", "fieldtype": "Data", "width": 120},
        {"label": _("Average %"), "fieldname": "avg_percentage", "fieldtype": "Percent", "width": 100},
        {"label": _("Review"), "fieldname": "review_link", "fieldtype": "Link", "options": "KPI Review", "width": 180},
    ]

    return columns, data
