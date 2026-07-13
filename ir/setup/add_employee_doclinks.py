# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


REQUIRED_LINKS = [
    {"link_doctype": "Disciplinary Action", "link_fieldname": "accused"},
    {"link_doctype": "Contract of Employment", "link_fieldname": "employee"},
    {"link_doctype": "Incapacity Proceedings", "link_fieldname": "accused"},
    {"link_doctype": "Poor Performance", "link_fieldname": "employee"},
    {"link_doctype": "Appeal Against Outcome", "link_fieldname": "employee"},
    {"link_doctype": "NTA Enquiry", "link_fieldname": "employee"},
    {"link_doctype": "Written Outcome", "link_fieldname": "employee"},
    {"link_doctype": "Not Guilty Form", "link_fieldname": "employee"},
    {"link_doctype": "Warning Form", "link_fieldname": "employee"},
    {"link_doctype": "Suspension Form", "link_fieldname": "employee"},
    {"link_doctype": "Demotion Form", "link_fieldname": "employee"},
    {"link_doctype": "Pay Deduction Form", "link_fieldname": "employee"},
    {"link_doctype": "Pay Reduction Form", "link_fieldname": "employee"},
    {"link_doctype": "Dismissal Form", "link_fieldname": "employee"},
    {"link_doctype": "Voluntary Seperation Agreement", "link_fieldname": "employee"},
    {"link_doctype": "Hearing Cancellation Form", "link_fieldname": "employee"},
    {
        "link_doctype": "KPI Review Employees",
        "link_fieldname": "employee",
        "parent_doctype": "KPI Review",
        "table_fieldname": "employees",
        "is_child_table": 1,
    },
    {"link_doctype": "Termination Form", "link_fieldname": "requested_for"},
    {"link_doctype": "Employee Induction Tracking", "link_fieldname": "employee"},
    {"link_doctype": "Status Change Form", "link_fieldname": "employee"},
    {"link_doctype": "Site Transfer Form", "link_fieldname": "employee"},
]


def _key(link):
    return (
        link.get("link_doctype") or "",
        link.get("link_fieldname") or "",
        link.get("parent_doctype") or "",
        link.get("table_fieldname") or "",
        int(link.get("is_child_table") or 0),
    )


def ensure_employee_links():
    """Replace the obsolete NTA Hearing link and ensure all required Employee links."""
    frappe.db.delete(
        "DocType Link",
        {
            "parent": "Employee",
            "parenttype": "DocType",
            "link_doctype": "NTA Hearing",
        },
    )

    existing = frappe.get_all(
        "DocType Link",
        filters={"parent": "Employee", "parenttype": "DocType"},
        fields=[
            "link_doctype",
            "link_fieldname",
            "parent_doctype",
            "table_fieldname",
            "is_child_table",
        ],
    )
    existing_keys = {_key(row) for row in existing}

    for link in REQUIRED_LINKS:
        if _key(link) in existing_keys:
            continue
        frappe.get_doc(
            {
                "doctype": "DocType Link",
                "parent": "Employee",
                "parentfield": "links",
                "parenttype": "DocType",
                "group": "Industrial Relations",
                **link,
            }
        ).insert(ignore_permissions=True)
