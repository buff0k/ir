# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from markdownify import markdownify as md

LEGACY_DOCTYPE = "Disciplinary Outcome Report"

FIELDS_TO_CONVERT = (
    "introduction",
    "complainant_case",
    "accused_case",
    "analysis_of_evidence",
    "finding",
    "mitigating_considerations",
    "aggravating_conisderations",
    "outcome",
)


def execute():
    if not frappe.db.exists("DocType", LEGACY_DOCTYPE):
        return

    available_fields = [
        fieldname
        for fieldname in FIELDS_TO_CONVERT
        if frappe.db.has_column(LEGACY_DOCTYPE, fieldname)
    ]

    if not available_fields:
        return

    reports = frappe.get_all(
        LEGACY_DOCTYPE,
        fields=["name", *available_fields],
    )

    for report in reports:
        values = {}

        for fieldname in available_fields:
            content = report.get(fieldname)
            if content:
                values[fieldname] = md(content)

        if values:
            frappe.db.set_value(
                LEGACY_DOCTYPE,
                report.name,
                values,
                update_modified=False,
            )
