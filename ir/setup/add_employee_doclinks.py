# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


EMPLOYEE_DOCTYPE = "Employee"
LINK_GROUP = "Industrial Relations"


REQUIRED_LINKS = [
    {
        "link_doctype": "Disciplinary Action",
        "link_fieldname": "accused",
    },
    {
        "link_doctype": "Contract of Employment",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Incapacity Proceedings",
        "link_fieldname": "accused",
    },
    {
        "link_doctype": "Poor Performance",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Appeal Against Outcome",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "NTA Enquiry",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Written Outcome",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "No Further Action Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Warning Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Suspension Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Demotion Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Pay Deduction Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Pay Reduction Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Dismissal Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Voluntary Seperation Agreement",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "KPI Review Employees",
        "link_fieldname": "employee",
        "parent_doctype": "KPI Review",
        "table_fieldname": "employees",
        "is_child_table": 1,
    },
    {
        "link_doctype": "Termination Form",
        "link_fieldname": "requested_for",
    },
    {
        "link_doctype": "Employee Induction Tracking",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Status Change Form",
        "link_fieldname": "employee",
    },
    {
        "link_doctype": "Site Transfer Form",
        "link_fieldname": "employee",
    },
]


OBSOLETE_LINK_DOCTYPES = {
    "NTA Hearing",
    "Disciplinary Outcome Report",
    "Not Guilty Form",
    "Performance Improved",
}


def ensure_employee_links():
    """
    Synchronise the Industrial Relations links shown on Employee.

    Behaviour:
    - removes explicitly retired DocType links;
    - removes IR links whose target DocType no longer exists;
    - removes malformed links whose configured field no longer exists;
    - removes duplicate IR links;
    - creates only currently valid required links;
    - leaves links belonging to other apps/groups untouched.
    """
    if not frappe.db.exists("DocType", EMPLOYEE_DOCTYPE):
        return

    _remove_obsolete_links()
    _remove_invalid_ir_links()
    _remove_duplicate_ir_links()
    _add_missing_links()


def _remove_obsolete_links():
    for doctype in OBSOLETE_LINK_DOCTYPES:
        frappe.db.delete(
            "DocType Link",
            {
                "parent": EMPLOYEE_DOCTYPE,
                "parenttype": "DocType",
                "link_doctype": doctype,
            },
        )


def _remove_invalid_ir_links():
    existing_links = _get_existing_ir_links()

    for link in existing_links:
        if _is_valid_link(link):
            continue

        frappe.db.delete("DocType Link", link.name)


def _remove_duplicate_ir_links():
    existing_links = _get_existing_ir_links()
    seen = set()

    for link in existing_links:
        key = _key(link)

        if key not in seen:
            seen.add(key)
            continue

        frappe.db.delete("DocType Link", link.name)


def _add_missing_links():
    existing_keys = {
        _key(link)
        for link in _get_existing_ir_links()
        if _is_valid_link(link)
    }

    for link in REQUIRED_LINKS:
        if not _is_valid_link(link):
            continue

        key = _key(link)

        if key in existing_keys:
            continue

        frappe.get_doc(
            {
                "doctype": "DocType Link",
                "parent": EMPLOYEE_DOCTYPE,
                "parentfield": "links",
                "parenttype": "DocType",
                "group": LINK_GROUP,
                **link,
            }
        ).insert(ignore_permissions=True)

        existing_keys.add(key)


def _get_existing_ir_links():
    return frappe.get_all(
        "DocType Link",
        filters={
            "parent": EMPLOYEE_DOCTYPE,
            "parenttype": "DocType",
            "group": LINK_GROUP,
        },
        fields=[
            "name",
            "link_doctype",
            "link_fieldname",
            "parent_doctype",
            "table_fieldname",
            "is_child_table",
        ],
        order_by="idx asc, creation asc",
    )


def _is_valid_link(link):
    link_doctype = _value(link, "link_doctype")
    link_fieldname = _value(link, "link_fieldname")
    is_child_table = int(_value(link, "is_child_table") or 0)

    if not link_doctype or not link_fieldname:
        return False

    if link_doctype in OBSOLETE_LINK_DOCTYPES:
        return False

    if not frappe.db.exists("DocType", link_doctype):
        return False

    if not frappe.db.has_column(link_doctype, link_fieldname):
        return False

    if not is_child_table:
        return True

    parent_doctype = _value(link, "parent_doctype")
    table_fieldname = _value(link, "table_fieldname")

    if not parent_doctype or not table_fieldname:
        return False

    if not frappe.db.exists("DocType", parent_doctype):
        return False

    parent_meta = frappe.get_meta(parent_doctype)
    table_field = parent_meta.get_field(table_fieldname)

    if not table_field:
        return False

    if table_field.fieldtype not in ("Table", "Table MultiSelect"):
        return False

    return table_field.options == link_doctype


def _key(link):
    return (
        _value(link, "link_doctype") or "",
        _value(link, "link_fieldname") or "",
        _value(link, "parent_doctype") or "",
        _value(link, "table_fieldname") or "",
        int(_value(link, "is_child_table") or 0),
    )


def _value(link, fieldname):
    if isinstance(link, dict):
        return link.get(fieldname)

    return getattr(link, fieldname, None)