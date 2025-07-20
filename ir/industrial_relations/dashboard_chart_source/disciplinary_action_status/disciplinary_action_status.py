# Copyright (c) 2025, buff0k and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import add_months

def get(chart_name=None, filters=None, from_date=None, to_date=None,
        timespan=None, time_interval=None, heatmap_year=None):

    end_date = frappe.utils.today()
    start_date = add_months(end_date, -3)

    branches = frappe.get_all("Branch", fields=["name"], order_by="name")
    outcomes = frappe.get_all("Offence Outcome", fields=["name"], order_by="name")

    labels = [outcome.name for outcome in outcomes] + ["Pending"]
    datasets = []

    color_palette = [
        "#7cd6fd", "#743ee2", "#5e64ff", "#ff5858", "#ffa00a",
        "#feef72", "#28a745", "#ff007c", "#dc3545", "#343a40"
    ]

    for i, branch in enumerate(branches):
        branch_counts = []

        for outcome in outcomes:
            count = frappe.db.count("Disciplinary Action", {
                "branch": branch.name,
                "outcome": outcome.name,
                "docstatus": 1,
                "creation": ["between", [start_date, end_date]]
            })
            branch_counts.append(count)

        pending = frappe.db.count("Disciplinary Action", {
            "branch": branch.name,
            "docstatus": 0,
            "creation": ["between", [start_date, end_date]]
        })
        branch_counts.append(pending)

        # Fallback color logic
        color = color_palette[i % len(color_palette)] if i < len(color_palette) else "#cccccc"

        datasets.append({
            "name": branch.name,
            "values": branch_counts,
            "color": color
        })

    return {
        "labels": labels,
        "datasets": datasets
    }
