# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


def get(chart_name=None, chart=None, no_cache=None, filters=None):
    to_date = getdate(nowdate())
    from_date = add_days(to_date, -30)

    labels = []
    current = from_date
    while current <= to_date:
        labels.append(str(current))
        current = add_days(current, 1)

    opened_rows = frappe.db.sql(
        """
        SELECT DATE(request_date) AS dt, COUNT(*) AS total
        FROM `tabDisciplinary Action`
        WHERE docstatus < 2
          AND request_date IS NOT NULL
          AND DATE(request_date) BETWEEN %s AND %s
        GROUP BY DATE(request_date)
        ORDER BY DATE(request_date)
        """,
        (from_date, to_date),
        as_dict=True,
    )

    closed_rows = frappe.db.sql(
        """
        SELECT DATE(outcome_date) AS dt, COUNT(*) AS total
        FROM `tabDisciplinary Action`
        WHERE docstatus < 2
          AND outcome_date IS NOT NULL
          AND DATE(outcome_date) BETWEEN %s AND %s
        GROUP BY DATE(outcome_date)
        ORDER BY DATE(outcome_date)
        """,
        (from_date, to_date),
        as_dict=True,
    )

    opened_map = {str(row.dt): row.total for row in opened_rows}
    closed_map = {str(row.dt): row.total for row in closed_rows}

    return {
        "type": "line",
        "labels": labels,
        "datasets": [
            {"name": _("Opened"), "values": [opened_map.get(label, 0) for label in labels]},
            {"name": _("Closed"), "values": [closed_map.get(label, 0) for label in labels]},
        ],
    }