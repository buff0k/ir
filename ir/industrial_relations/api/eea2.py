# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.data import cint
from ir.industrial_relations.report.employment_equity_report.employment_equity_report import execute as eea2_execute

@frappe.whitelist()
def get_eea2_data(filters=None):
    try:
        filters = frappe.parse_json(filters) if filters is not None else {}
    except Exception:
        filters = {}

    if not filters.get("company") or not filters.get("country"):
        frappe.throw("Please select both Company and Country")

    _, rows = eea2_execute({
        "company": filters["company"],
        "country": filters["country"],
        "disabled": cint(filters.get("disabled")),
        "branch": (filters.get("branch") or "").strip(),
    })
    return {"rows": rows}
