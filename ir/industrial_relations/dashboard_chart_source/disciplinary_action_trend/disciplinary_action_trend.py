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

    # "Currently Open" is a true running balance - opened-so-far minus
    # closed-so-far, as of each day X - not today's docstatus backdated
    # onto every past day (an earlier version of this did exactly that,
    # which both hides a record's open days once it's since been closed
    # and drops one that was open in the past but has since been
    # cancelled). A real backlog needs every opened/closed event up to
    # to_date - not just the ones inside the visible window - since a case
    # opened before the window started, still unresolved, is still part of
    # the backlog on day one of the window.
    #
    # "Closed" here is the record's actual submit date, not outcome_date -
    # outcome_date is a plain Date field the IR practitioner fills in
    # before submitting (required by before_submit()'s require_outcome_
    # before_submit check), so it can already be set while the record is
    # still sitting in Draft, days or weeks before it's actually
    # submitted. modified is a reliable stand-in for the submit timestamp
    # specifically because this doctype has zero allow_on_submit fields
    # (confirmed against its own DocType JSON) - nothing can touch a
    # submitted record afterwards, so a currently-submitted record's
    # modified date is exactly the moment it was submitted.
    all_opened_dates = sorted(
        getdate(d)
        for d in frappe.db.sql_list(
            """
            SELECT request_date
            FROM `tabDisciplinary Action`
            WHERE docstatus < 2 AND request_date IS NOT NULL AND DATE(request_date) <= %s
            """,
            (to_date,),
        )
    )
    all_closed_dates = sorted(
        getdate(d)
        for d in frappe.db.sql_list(
            """
            SELECT modified
            FROM `tabDisciplinary Action`
            WHERE docstatus = 1 AND DATE(modified) <= %s
            """,
            (to_date,),
        )
    )

    opened_map = {str(row.dt): row.total for row in opened_rows}
    closed_map = {str(row.dt): row.total for row in closed_rows}

    currently_open_map = {}
    opened_idx = closed_idx = 0
    opened_count = closed_count = 0
    for label in labels:
        label_date = getdate(label)
        while opened_idx < len(all_opened_dates) and all_opened_dates[opened_idx] <= label_date:
            opened_count += 1
            opened_idx += 1
        while closed_idx < len(all_closed_dates) and all_closed_dates[closed_idx] <= label_date:
            closed_count += 1
            closed_idx += 1
        currently_open_map[label] = opened_count - closed_count

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