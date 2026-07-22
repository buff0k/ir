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
    "Written Outcome": "employee_designation",
    "Warning Form": "position",
    "Suspension Form": "position",
    "Dismissal Form": "position",
    "Demotion Form": "position",
    "Pay Deduction Form": "position",
    "Pay Reduction Form": "position",
    "No Further Action Form": "designation",
    "Appeal Against Outcome": "position",
}

# Doctype -> fieldname holding the Employee link whose Employee.branch is checked
# against a user's "Responsible HR per Branch" (hr_per_branch) rows on IR Role
# Restrictions. Deliberately does not include External Dispute Resolution (no single
# branch - it's inherently multi-employee/multi-branch), NTA Enquiry, or Written
# Outcome.
BRANCH_LIMITED_DOCTYPES = {
    "Disciplinary Action": "accused",
    "Incapacity Proceedings": "accused",
    "Poor Performance": "employee",
    "Warning Form": "employee",
    "Suspension Form": "employee",
    "Dismissal Form": "employee",
    "Demotion Form": "employee",
    "Pay Deduction Form": "employee",
    "Pay Reduction Form": "employee",
    "No Further Action Form": "employee",
    "Appeal Against Outcome": "employee",
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


def responsible_branches_for_user(user: str | None = None, parentfield: str = "hr_per_branch") -> list[str]:
    """Branches a user is responsible for, from IR Role Restrictions (hr_per_branch by
    default). An empty list means the branch limit doesn't apply to this user at all -
    callers must treat that as "no restriction", not "restricted from everything"."""
    user = user or frappe.session.user
    rows = frappe.get_all(
        "IR Role Restrictions User Branch",
        filters={
            "parent": "IR Role Restrictions",
            "parenttype": "IR Role Restrictions",
            "parentfield": parentfield,
            "user": user,
        },
        fields=["branch"],
    )
    return [row.branch for row in rows if row.get("branch")]


def _employee_branch(employee: str | None) -> str | None:
    if not employee:
        return None
    return frappe.db.get_value("Employee", employee, "branch")


def _branch_is_restricted(doctype: str, employee: str | None, user: str | None = None) -> bool:
    """True only if this user has hr_per_branch rows (branch limits apply to them at
    all) AND the employee's branch isn't among them. No rows -> designation-only
    fallback, per design."""
    if doctype not in BRANCH_LIMITED_DOCTYPES:
        return False

    branches = responsible_branches_for_user(user)
    if not branches:
        return False

    return _employee_branch(employee) not in branches


def _sql_branch_condition(doctype: str, employee_field: str, user: str | None) -> str | None:
    branches = responsible_branches_for_user(user)
    if not branches:
        return None
    escaped = ", ".join(frappe.db.escape(value) for value in branches)
    return (
        f"`tab{doctype}`.`{employee_field}` IN "
        f"(SELECT name FROM `tabEmployee` WHERE branch IN ({escaped}))"
    )


def _permission_query(doctype: str, user: str | None) -> str:
    conditions = []

    restricted = restricted_designations_for_user(user)
    if restricted:
        fieldname = DESIGNATION_FIELD_BY_DOCTYPE[doctype]
        conditions.append(_sql_not_in_designations(f"`tab{doctype}`.`{fieldname}`", restricted))

    employee_field = BRANCH_LIMITED_DOCTYPES.get(doctype)
    if employee_field:
        branch_condition = _sql_branch_condition(doctype, employee_field, user)
        if branch_condition:
            conditions.append(branch_condition)

    return " and ".join(conditions)


def _designation_is_restricted(designation: str | None, user: str | None = None) -> bool:
    return bool(designation) and designation in set(restricted_designations_for_user(user))


def _has_permission(doc, fieldname: str, user: str | None = None, ptype: str | None = None) -> bool:
    user = user or frappe.session.user
    if not effective_ir_role(user):
        return True
    if ptype not in PROTECTED_PERMISSION_TYPES:
        return True
    if _designation_is_restricted(doc.get(fieldname), user):
        return False

    employee_field = BRANCH_LIMITED_DOCTYPES.get(doc.doctype)
    if employee_field and _branch_is_restricted(doc.doctype, doc.get(employee_field), user):
        return False

    return True


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


def recipient_passes_restrictions(doc, user: str | None) -> bool:
    """Whether `user` would be permitted to view `doc`, combining Designation Limits
    and Branch Limits (where applicable). Used to decide whether to include `user` as
    a notification recipient - the same filtering that gates record visibility."""
    if not user or not effective_ir_role(user):
        return True

    designation_field = DESIGNATION_FIELD_BY_DOCTYPE.get(doc.doctype)
    if designation_field and _designation_is_restricted(doc.get(designation_field), user):
        return False

    employee_field = BRANCH_LIMITED_DOCTYPES.get(doc.doctype)
    if employee_field and _branch_is_restricted(doc.doctype, doc.get(employee_field), user):
        return False

    return True


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


def warning_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Warning Form", user)


def suspension_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Suspension Form", user)


def dismissal_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Dismissal Form", user)


def demotion_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Demotion Form", user)


def pay_deduction_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Pay Deduction Form", user)


def pay_reduction_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Pay Reduction Form", user)


def no_further_action_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("No Further Action Form", user)


def appeal_against_outcome_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Appeal Against Outcome", user)


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
    return _has_permission(doc, "employee_designation", user, ptype)


def warning_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def suspension_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def dismissal_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def demotion_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def pay_deduction_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def pay_reduction_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "position", user, ptype)


def no_further_action_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, "designation", user, ptype)


def appeal_against_outcome_has_permission(doc, user=None, ptype=None) -> bool:
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
    _validate_designation(doc, "employee_designation")


def validate_warning_form(doc, method=None):
    _validate_designation(doc, "position")


def validate_suspension_form(doc, method=None):
    _validate_designation(doc, "position")


def validate_dismissal_form(doc, method=None):
    _validate_designation(doc, "position")


def validate_demotion_form(doc, method=None):
    _validate_designation(doc, "position")


def validate_pay_deduction_form(doc, method=None):
    _validate_designation(doc, "position")


def validate_pay_reduction_form(doc, method=None):
    _validate_designation(doc, "position")


def validate_no_further_action_form(doc, method=None):
    _validate_designation(doc, "designation")


def validate_appeal_against_outcome(doc, method=None):
    _validate_designation(doc, "position")
