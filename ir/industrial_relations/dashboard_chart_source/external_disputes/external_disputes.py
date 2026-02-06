# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _

@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None,
        from_date=None, to_date=None, timespan=None, time_interval=None,
        heatmap_year=None):
    submitted = frappe.db.count("External Dispute Resolution", {"docstatus": 1})
    saved = frappe.db.count("External Dispute Resolution", {"docstatus": 0})

    return {
        "labels": [_("Concluded"), _("Pending")],
        "datasets": [{"name": _("Documents"), "values": [submitted, saved]}],
        "type": "pie",
    }
