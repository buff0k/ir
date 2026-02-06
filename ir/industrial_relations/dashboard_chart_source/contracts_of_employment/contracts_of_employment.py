# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _

@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None,
        from_date=None, to_date=None, timespan=None, time_interval=None,
        heatmap_year=None):
    if isinstance(filters, str):
        try:
            filters = frappe.parse_json(filters)
        except Exception:
            filters = {}
    filters = filters or {}

    cond = {}
    if filters.get("branch"):
        cond["branch"] = filters["branch"]

    submitted = frappe.db.count("Contract of Employment", {"docstatus": 1, **cond})
    saved = frappe.db.count("Contract of Employment", {"docstatus": 0, **cond})

    return {
        "labels": [_("Concluded"), _("Awaiting Signature")],
        "datasets": [{"name": _("Documents"), "values": [submitted, saved]}],
        "type": "pie",
    }
