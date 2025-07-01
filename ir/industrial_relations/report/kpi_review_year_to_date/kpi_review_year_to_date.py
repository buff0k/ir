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

    scoring_kpi_field = "kpi"
    scoring_score_field = "score"
    scoring_max_score_field = "max_score"

    group_query = f"""
        SELECT 
            branch AS site,
            kpi_template,
            COUNT(name) AS total_reviews,
            SUM(CAST(SUBSTRING_INDEX(score, ' ', 1) AS DECIMAL(10,2))) AS total_score,
            SUM(CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(score, '/', -1), '(', 1) AS DECIMAL(10,2))) AS total_possible,
            ROUND(AVG(CAST(TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1)) AS DECIMAL(10,2))), 2) AS avg_percentage
        FROM `tabKPI Review`
        {where_clause}
        GROUP BY branch, kpi_template
        ORDER BY branch, kpi_template
    """

    detail_query = f"""
        SELECT
            kpr.branch AS site,
            kpr.kpi_template,
            kpr.name AS review_name,
            kpr.score,
            IFNULL(
                GROUP_CONCAT(CONCAT(s.{scoring_kpi_field}, ': ', s.{scoring_score_field}, '/', s.{scoring_max_score_field}) ORDER BY s.idx SEPARATOR ', '),
                ''
            ) AS parent_kpi_scores
        FROM `tabKPI Review` kpr
        LEFT JOIN `tabKPI Review Scoring` s 
            ON s.parent = kpr.name 
            AND s.{scoring_kpi_field} IS NOT NULL
        {where_clause}
        GROUP BY kpr.name
    """

    groups = frappe.db.sql(group_query, values, as_dict=True)
    details = frappe.db.sql(detail_query, values, as_dict=True)

    data = []

    for g in groups:
        total_score = g.total_score or 0
        total_possible = g.total_possible or 0

        avg_score = f"{total_score:.2f}/{total_possible:.2f}" if total_possible else "-"

        data.append({
            "site": g.site or "(No Site)",
            "kpi_template": g.kpi_template,
            "total_reviews": g.total_reviews,
            "avg_score": avg_score,
            "avg_percentage": round(g.avg_percentage or 0, 2),
            "review_link": "",
            "parent_kpis": "",
            "is_group": 1
        })

        for d in details:
            if d.site == g.site and d.kpi_template == g.kpi_template:
                score_display = "-"
                avg_pct = 0

                if d.score:
                    parts = d.score.split("/")
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].split("(")[0].strip()
                        try:
                            left_val = float(left)
                            right_val = float(right)
                            score_display = f"{left_val:.2f}/{right_val:.2f}"
                        except:
                            score_display = f"{left}/{right}"
                        if "(" in d.score and "%" in d.score:
                            pct_part = d.score.split("(")[-1].replace("%", "").replace(")", "").strip()
                            try:
                                avg_pct = float(pct_part)
                            except:
                                avg_pct = 0

                site_label = d.site or "(No Site)"
                link_value = d.review_name or ""

                data.append({
                    "site": f"↳ {site_label}",
                    "kpi_template": "",
                    "total_reviews": "",
                    "avg_score": score_display,
                    "avg_percentage": avg_pct,
                    "review_link": link_value,
                    "parent_kpis": d.parent_kpi_scores or "(No Parent KPIs)",
                    "is_group": 0
                })

    columns = [
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 120},
        {"label": _("KPI Template"), "fieldname": "kpi_template", "fieldtype": "Link", "options": "KPI Template", "width": 200},
        {"label": _("Total Reviews"), "fieldname": "total_reviews", "fieldtype": "Int", "width": 100},
        {"label": _("Average Score"), "fieldname": "avg_score", "fieldtype": "Data", "width": 120},
        {"label": _("Average %"), "fieldname": "avg_percentage", "fieldtype": "Percent", "width": 100},
        {"label": _("Review"), "fieldname": "review_link", "fieldtype": "Link", "options": "KPI Review", "width": 180},
        {"label": _("Parent KPI Scores"), "fieldname": "parent_kpis", "fieldtype": "Data", "width": 300},
    ]

    return columns, data
