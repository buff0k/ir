# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate
from frappe.utils.dashboard import cache_source

@frappe.whitelist()
@cache_source
def get(
    chart_name=None,
    chart=None,
    no_cache=None,
    filters=None,
    from_date=None,
    to_date=None,
    time_interval=None,
    timespan=None,
    heatmap_year=None,
):
    to_date = getdate(to_date) if to_date else getdate(nowdate())
    from_date = getdate(from_date) if from_date else add_days(to_date, -30)

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

    # "Currently Open" is a running backlog total, not a per-day new-draft
    # count like Opened/Closed above - most of today's Draft records were
    # requested well before this chart's visible window (a case opened 2
    # months ago and still unresolved is still part of today's backlog),
    # so bucketing by "requested on this exact day" would hide almost all
    # of them. Instead: for each day X in the window, count every record
    # that is a Draft right now AND was already requested on or before X -
    # an approximation (docstatus only reflects this record's state today,
    # there's no per-day history of it), but the right one here: it's
    # exactly "how many of today's open cases had already been raised by
    # day X", which is what a backlog line is for.
    currently_open_dates = sorted(
        getdate(d)
        for d in frappe.db.sql_list(
            """
            SELECT request_date
            FROM `tabDisciplinary Action`
            WHERE docstatus = 0 AND request_date IS NOT NULL
            """
        )
    )

    opened_map = {str(row.dt): row.total for row in opened_rows}
    closed_map = {str(row.dt): row.total for row in closed_rows}

    currently_open_map = {}
    running_total = 0
    next_idx = 0
    for label in labels:
        label_date = getdate(label)
        while next_idx < len(currently_open_dates) and currently_open_dates[next_idx] <= label_date:
            running_total += 1
            next_idx += 1
        currently_open_map[label] = running_total

    return {
        "labels": labels,
        "datasets": [
            {"name": _("Opened"), "values": [opened_map.get(label, 0) for label in labels]},
            {"name": _("Closed"), "values": [closed_map.get(label, 0) for label in labels]},
            {
                "name": _("Currently Open (Draft Status)"),
                "values": [currently_open_map.get(label, 0) for label in labels],
            },
        ],
    }