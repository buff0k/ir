# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    # ---------- shared values ----------
    values = {}

    # Base conditions (no alias) for group & chart queries
    base_conds = ["docstatus = 1"]  # only submitted KPI Reviews

    if filters.get("year"):
        base_conds.append("YEAR(date_under_review) = %(year)s")
        values["year"] = filters["year"]

    if filters.get("site"):
        base_conds.append("branch = %(site)s")
        values["site"] = filters["site"]

    if filters.get("kpi_template"):
        base_conds.append("kpi_template = %(kpi_template)s")
        values["kpi_template"] = filters["kpi_template"]

    where_clause = "WHERE " + " AND ".join(base_conds) if base_conds else ""

    # Alias-aware conditions for the detail query (prefix KPI Review fields with kpr.)
    alias_conds = []
    for cond in base_conds:
        alias_conds.append(
            cond
            .replace("docstatus", "kpr.docstatus")
            .replace("date_under_review", "kpr.date_under_review")
            .replace("branch", "kpr.branch")
            .replace("kpi_template", "kpr.kpi_template")
        )
    where_clause_kpr = "WHERE " + " AND ".join(alias_conds) if alias_conds else ""

    scoring_kpi_field = "kpi"
    scoring_score_field = "score"
    scoring_max_score_field = "max_score"

    # -------- group query --------
    group_query = f"""
        SELECT 
            branch AS site,
            kpi_template,
            COUNT(name) AS total_reviews,
            ROUND(
                AVG(
                    CAST(
                        TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1))
                        AS DECIMAL(10,2)
                    )
                ), 2
            ) AS avg_percentage
        FROM `tabKPI Review`
        {where_clause}
        GROUP BY branch, kpi_template
        ORDER BY branch, kpi_template
    """

    # -------- detail query (uses alias-aware WHERE) --------
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
        {where_clause_kpr}
        GROUP BY kpr.name
    """

    # -------- chart query --------
    chart_query = f"""
        SELECT 
            branch AS site,
            MONTH(date_under_review) AS review_month,
            ROUND(
                AVG(
                    CAST(
                        TRIM(TRAILING '%%' FROM SUBSTRING_INDEX(SUBSTRING_INDEX(score, '(', -1), '%%', 1))
                        AS DECIMAL(10,2)
                    )
                ), 2
            ) AS avg_percentage
        FROM `tabKPI Review`
        {where_clause}
        GROUP BY branch, MONTH(date_under_review)
        ORDER BY branch, MONTH(date_under_review)
    """

    groups = frappe.db.sql(group_query, values, as_dict=True)
    details = frappe.db.sql(detail_query, values, as_dict=True)
    chart_rows = frappe.db.sql(chart_query, values, as_dict=True)

    # ---- remainder of your function unchanged ----
    data = []

    for g in groups:
        children = [d for d in details if d.site == g.site and d.kpi_template == g.kpi_template]

        numerators, denominators = [], []
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

        avg_numerator = sum(numerators) / len(numerators) if numerators else 0
        avg_denominator = sum(denominators) / len(denominators) if denominators else 0
        avg_score = f"{round(avg_numerator, 2):.2f}/{round(avg_denominator, 2):.2f}" if avg_denominator else "-"

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

    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    sites = {}
    for row in chart_rows:
        site = row.site or "Unknown"
        month_idx = int(row.review_month) - 1 if row.review_month else 0
        if site not in sites:
            sites[site] = [None] * 12
        sites[site][month_idx] = row.avg_percentage

    datasets = [{"name": site, "values": values} for site, values in sites.items()]

    chart = {"data": {"labels": months, "datasets": datasets}, "type": "line"}

    return columns, data, None, chart
