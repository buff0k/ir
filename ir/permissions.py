# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _

IR_ROLE_ORDER = ("IR Manager", "IR Officer", "IR User")
PROTECTED_PERMISSION_TYPES = {
    None,
    "read",
    "create",
    "write",
    "submit",
    "cancel",
    "delete",
    "print",
    "email",
    "report",
    "export",
}

DESIGNATION_FIELD_BY_DOCTYPE = {
    "Contract of Employment": "designation",
    "Disciplinary Action": "accused_pos",
    "Incapacity Proceedings": "accused_pos",
    "Poor Performance": "employee_designation",
    "NTA Enquiry": "position",
    "Written Outcome": "position",
}


def effective_ir_role(user: str | None = None) -> str | None:
    """Return the user's highest IR role: Manager, Officer, then User."""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return next((role for role in IR_ROLE_ORDER if role in roles), None)


def restricted_designations_for_user(user: str | None = None) -> list[str]:
    """Read designation restrictions directly from IR Role Restrictions."""
    user = user or frappe.session.user
    role = effective_ir_role(user)
    if not role:
        return []

    parentfield_by_role = {
        "IR Manager": "ir_manager_restrictions",
        "IR Officer": "ir_officer_restrictions",
        "IR User": "ir_user_restrictions",
    }

    rows = frappe.get_all(
        "IR Role Restriction Table",
        filters={
            "parent": "IR Role Restrictions",
            "parenttype": "IR Role Restrictions",
            "parentfield": parentfield_by_role[role],
        },
        fields=["designation"],
        order_by="idx asc",
    )
    return [row.designation for row in rows if row.get("designation")]


def _sql_not_in_designations(field_sql: str, designations: list[str]) -> str:
    if not designations:
        return "1=1"
    escaped = ", ".join(frappe.db.escape(value) for value in designations)
    return f"({field_sql} IS NULL OR {field_sql} = '' OR {field_sql} NOT IN ({escaped}))"


def _permission_query(doctype: str, user: str | None) -> str:
    restricted = restricted_designations_for_user(user)
    if not restricted:
        return ""
    fieldname = DESIGNATION_FIELD_BY_DOCTYPE[doctype]
    return _sql_not_in_designations(f"`tab{doctype}`.`{fieldname}`", restricted)


def _designation_is_restricted(designation: str | None, user: str | None = None) -> bool:
    return bool(designation) and designation in set(restricted_designations_for_user(user))


def _has_permission(doc, fieldname: str, user: str | None = None, ptype: str | None = None) -> bool:
    user = user or frappe.session.user
    if not effective_ir_role(user):
        return True
    if ptype not in PROTECTED_PERMISSION_TYPES:
        return True
    return not _designation_is_restricted(doc.get(fieldname), user)


def _validate_designation(doc, fieldname: str, user: str | None = None) -> None:
    user = user or frappe.session.user
    if not effective_ir_role(user):
        return
    designation = doc.get(fieldname)
    if _designation_is_restricted(designation, user):
        frappe.throw(
            _("You are not permitted to create or edit this document for designation: {0}").format(designation),
            frappe.PermissionError,
        )


# Permission query hooks

def contract_of_employment_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Contract of Employment", user)


def disciplinary_action_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Disciplinary Action", user)


def incapacity_proceedings_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Incapacity Proceedings", user)


def poor_performance_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Poor Performance", user)


def nta_enquiry_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("NTA Enquiry", user)


def written_outcome_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Written Outcome", user)


# Direct-access permission hooks

def contract_of_employment_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "designation", user, ptype)


def disciplinary_action_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "accused_pos", user, ptype)


def incapacity_proceedings_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "accused_pos", user, ptype)


def poor_performance_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "employee_designation", user, ptype)


def nta_enquiry_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def written_outcome_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


# Validation hooks

def validate_contract_of_employment(doc, method=None):
    _validate_designation(doc, "designation")


def validate_disciplinary_action(doc, method=None):
    _validate_designation(doc, "accused_pos")


def validate_incapacity_proceedings(doc, method=None):
    _validate_designation(doc, "accused_pos")


def validate_poor_performance(doc, method=None):
    _validate_designation(doc, "employee_designation")


def validate_nta_enquiry(doc, method=None):
    _validate_designation(doc, "position")


def validate_written_outcome(doc, method=None):
    _validate_designation(doc, "position")
