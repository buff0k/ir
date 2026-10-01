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
    {
        "link_doctype": "Retrenchment Affected Employee",
        "link_fieldname": "employee",
        "parent_doctype": "Retrenchment Process",
        "table_fieldname": "affected_employees",
        "is_child_table": 1,
    },
    {
        "link_doctype": "Section 189 Notice Recipient",
        "link_fieldname": "employee",
        "parent_doctype": "Section 189 Notice",
        "table_fieldname": "recipients",
        "is_child_table": 1,
    },
    {
        "link_doctype": "S189 Consultation Attendee",
        "link_fieldname": "employee",
        "parent_doctype": "S189 Consultation",
        "table_fieldname": "attendees",
        "is_child_table": 1,
    },
    {
        # Not is_child_table: that shape feeds Frappe's internal_links/
        # get_internal_links(), which only resolves a count when VIEWING the
        # doctype that owns the child table (e.g. open a Retrenchment
        # Process, see its Affected Employees) - never the reverse. Viewed
        # from Employee, it always reads 0 and silently falls back to the
        # single *global* fieldname guess shared by every doctype on this
        # page (whichever non-child link was registered first with a given
        # link_fieldname - here "employee"), which only coincidentally
        # matches the other entries above because their own child-table
        # field also happens to be named "employee". External Dispute
        # Resolution's real field is "applicant", so that fallback misses
        # entirely and the connection always shows 0.
        #
        # A plain entry instead makes add_doctype_links() record this exact
        # fieldname in non_standard_fieldnames, which get_external_links()
        # uses directly - frappe.get_all(doctype, filters={fieldname: ...})
        # already auto-resolves against a doctype's own child table when the
        # field isn't a direct column (confirmed directly: filtering
        # External Dispute Resolution by applicant=<employee> returns the
        # real matching matters), so no is_child_table bookkeeping is needed
        # here at all - see _doctype_or_child_table_has_field() below.
        "link_doctype": "External Dispute Resolution",
        "link_fieldname": "applicant",
    },
]


OBSOLETE_LINK_DOCTYPES = {
    "NTA Hearing",
    "Disciplinary Outcome Report",
    "Not Guilty Form",
    "Performance Improved",
    # Replaced by a plain (non-is_child_table) link straight to "External
    # Dispute Resolution" - see the comment on that entry in REQUIRED_LINKS.
    "External Dispute Resolution Applicants",
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

    if not _doctype_or_child_table_has_field(link_doctype, link_fieldname):
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


def _doctype_or_child_table_has_field(doctype, fieldname):
    """A link_fieldname is valid either as a direct column on `doctype`, or
    as a column on one of `doctype`'s own child tables - frappe.get_all()
    already auto-resolves filters={fieldname: value} against a child table
    in exactly that second case (confirmed directly against this site's own
    data: filtering External Dispute Resolution by applicant=<employee>
    correctly matches via its applicant_history child table), so a plain
    (non-is_child_table) link entry doesn't need link_fieldname to be a
    direct column to actually work."""
    if frappe.db.has_column(doctype, fieldname):
        return True

    for table_field in frappe.get_meta(doctype).get_table_fields():
        if frappe.db.exists("DocType", table_field.options) and frappe.db.has_column(
            table_field.options, fieldname
        ):
            return True

    return False