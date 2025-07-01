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
        conditions.append("YEAR(date_under_review) = %(year)s")
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

    # Group query: only need avg percentage now
    group_query = f"""
        SELECT 
            branch AS site,
            kpi_template,
            COUNT(name) AS total_reviews,
            ROUND(AVG(CAST(TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1)) AS DECIMAL(10,2))), 2) AS avg_percentage
        FROM `tabKPI Review`
        {where_clause}
        GROUP BY branch, kpi_template
        ORDER BY branch, kpi_template
    """

    # Detail rows (children)
    detail_query = f"""
        SELECT
            kpr.branch AS site,
            kpr.kpi_template,
            kpr.name AS review_name,
            kpr.score,
            IFNULL(
                GROUP_CONCAT(
                    CONCAT(
                        s.{scoring_kpi_field}, ': ',
                        FORMAT(s.{scoring_score_field}, 2), '/', s.{scoring_max_score_field}
                    )
                    ORDER BY s.idx SEPARATOR ', '
                ),
                ''
            ) AS parent_kpi_scores
        FROM `tabKPI Review` kpr
        LEFT JOIN `tabKPI Review Scoring` s 
            ON s.parent = kpr.name AND s.{scoring_kpi_field} IS NOT NULL
        {where_clause}
        GROUP BY kpr.name
    """

    # Chart rows
    chart_query = f"""
        SELECT 
            branch AS site,
            MONTH(date_under_review) AS review_month,
            ROUND(AVG(CAST(TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1)) AS DECIMAL(10,2))), 2) AS avg_percentage
        FROM `tabKPI Review`
        {where_clause}
        GROUP BY branch, MONTH(date_under_review)
        ORDER BY branch, MONTH(date_under_review)
    """

    groups = frappe.db.sql(group_query, values, as_dict=True)
    details = frappe.db.sql(detail_query, values, as_dict=True)
    chart_rows = frappe.db.sql(chart_query, values, as_dict=True)

    data = []

    for g in groups:
        # Find matching children
        children = [d for d in details if d.site == g.site and d.kpi_template == g.kpi_template]

        numerators = []
        denominators = []

        for d in children:
            if d.score:
                parts = d.score.split("/")
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = d.score.split("/")[1].split("(")[0].strip()
                    try:
                        numerators.append(float(left))
                        denominators.append(float(right))
                    except:
                        pass

        if numerators:
            avg_numerator = sum(numerators) / len(numerators)
        else:
            avg_numerator = 0

        if denominators:
            avg_denominator = sum(denominators) / len(denominators)
        else:
            avg_denominator = 0

        if avg_denominator:
            avg_score = f"{round(avg_numerator, 2):.2f}/{round(avg_denominator, 2):.2f}"
        else:
            avg_score = "-"

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

        for d in children:
            score_display = "-"
            avg_pct = 0

            if d.score:
                parts = d.score.split("/")
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].split("(")[0].strip()
                    try:
                        left_val = round(float(left), 2)
                        right_val = round(float(right), 2)
                        score_display = f"{left_val:.2f}/{right_val:.2f}"
                    except:
                        score_display = "-"
                    if "(" in d.score and "%" in d.score:
                        pct_part = d.score.split("(")[-1].replace("%", "").replace(")", "").strip()
                        try:
                            avg_pct = float(pct_part)
                        except:
                            avg_pct = 0

            data.append({
                "site": f"↳ {d.site or '(No Site)'}",
                "kpi_template": "",
                "total_reviews": "",
                "avg_score": score_display,
                "avg_percentage": avg_pct,
                "review_link": d.review_name or "",
                "parent_kpis": d.parent_kpi_scores or "(No Parent KPIs)",
                "is_group": 0
            })

    columns = [
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 180},
        {"label": _("KPI Template"), "fieldname": "kpi_template", "fieldtype": "Link", "options": "KPI Template", "width": 100},
        {"label": _("Qty"), "fieldname": "total_reviews", "fieldtype": "Int", "width": 50},
        {"label": _("Overall Score"), "fieldname": "avg_score", "fieldtype": "Data", "width": 120},
        {"label": _("Overall %"), "fieldname": "avg_percentage", "fieldtype": "Percent", "width": 100},
        {"label": _("Review"), "fieldname": "review_link", "fieldtype": "Link", "options": "KPI Review", "width": 200},
        {"label": _("KPI Scores"), "fieldname": "parent_kpis", "fieldtype": "Data", "width": 400},
    ]

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    sites = {}
    for row in chart_rows:
        site = row.site or "Unknown"
        month_idx = int(row.review_month) - 1 if row.review_month else 0
        if site not in sites:
            sites[site] = [None] * 12
        sites[site][month_idx] = row.avg_percentage

    datasets = []
    for site, values in sites.items():
        datasets.append({
            "name": site,
            "values": values
        })

    chart = {
        "data": {
            "labels": months,
            "datasets": datasets
        },
        "type": "line"
    }

    return columns, data, None, chart
