# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations
import frappe
from frappe import _

def check_app_permission():
    """Check if the user has permission to access the app (for showing it on the app screen)"""
    # Administrator always has access
    if frappe.session.user == "Administrator":
        return True

    # Check if the user has any of the required roles
    required_roles = [
        "System Manager", "IR Manager", "IR User", "Payroll Manager", "Payroll User",
        "HR Manager", "HR User", "IR Officer", "Training Manager",
        "Training Facilitator", "Training Administrator"
    ]
    user_roles = frappe.get_roles(frappe.session.user)

    # Grant access if the user has at least one of the required roles
    if any(role in user_roles for role in required_roles):
        return True

    return False


# --------------------------------------------------------------------
# IR Role Restrictions (Designation-based)
# --------------------------------------------------------------------

_IR_ROLE_ORDER = ["IR Manager", "IR Officer", "IR User"]

def _effective_ir_role(user: str | None = None) -> str | None:
    """
    Highest IR role wins: IR Manager > IR Officer > IR User.
    Returns None if the user has none of these roles.
    """
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    for r in _IR_ROLE_ORDER:
        if r in roles:
            return r
    return None

def _restricted_designations_for_user(user: str | None = None) -> list[str]:
    """
    Returns a list of Designation names the user's effective IR role must NOT see.
    Reads from the singleton 'IR Role Restrictions' child tables using direct DB queries
    (avoids singleton doc caching in long-running processes).
    """
    user = user or frappe.session.user

    role = _effective_ir_role(user)
    if not role:
        return []

    parent = "IR Role Restrictions"  # Single DocType name is also the docname
    parenttype = "IR Role Restrictions"

    parentfield_by_role = {
        "IR Manager": "ir_manager_restrictions",
        "IR Officer": "ir_officer_restrictions",
        "IR User": "ir_user_restrictions",
    }
    parentfield = parentfield_by_role[role]

    # If the singleton hasn't been created/saved yet, these rows won't exist (fail open).
    rows = frappe.get_all(
        "IR Role Restriction Table",
        filters={
            "parenttype": parenttype,
            "parent": parent,
            "parentfield": parentfield,
        },
        fields=["designation"],
        order_by="idx asc",
    )

    return [r.designation for r in rows if r.get("designation")]


def _sql_not_in_designations(field_sql: str, designations: list[str]) -> str:
    """
    Build a safe SQL fragment:
      - Allow NULL/blank designation values through
      - Exclude rows where field_sql is in the restricted list
    """
    if not designations:
        return "1=1"

    escaped = ", ".join(frappe.db.escape(d) for d in designations)
    return f"({field_sql} IS NULL OR {field_sql} = '' OR {field_sql} NOT IN ({escaped}))"


# --------------------------------------------------------------------
# permission_query_conditions for key doctypes
#
# NOTE: These conditions will:
#   - hide matching documents from list views
#   - hide them from standard reports that use Frappe permissions
# --------------------------------------------------------------------

def contract_of_employment_permission_query_conditions(user: str) -> str:
    """
    DocType: Contract of Employment
    Fields:
      - employee (Link Employee) [not used for restriction]
      - designation (Link Designation) <-- restriction field
    """
    restricted = _restricted_designations_for_user(user)
    if not restricted:
        return ""

    return _sql_not_in_designations("`tabContract of Employment`.`designation`", restricted)

def disciplinary_action_permission_query_conditions(user: str) -> str:
    """
    DocType: Disciplinary Action
    Fields:
      - accused (Link Employee) [not used for restriction]
      - accused_pos (Link Designation) <-- restriction field
    """
    restricted = _restricted_designations_for_user(user)
    if not restricted:
        return ""

    return _sql_not_in_designations("`tabDisciplinary Action`.`accused_pos`", restricted)


# --------------------------------------------------------------------
# has_permission enforcement (blocks direct open by URL/name/API)
#
# Why needed:
# - permission_query_conditions filters list/report queries
# - but a user may still open a record directly if they know the name
# --------------------------------------------------------------------

def _is_designation_restricted_for_user(designation: str | None, user: str | None = None) -> bool:
    user = user or frappe.session.user
    if not designation:
        return False
    return designation in set(_restricted_designations_for_user(user))


def _raise_if_restricted_designation(doc, designation_field: str, user: str | None = None):
    """
    Server-side guard to prevent creating/updating a document with a restricted designation.
    Use this via doc_events validate/before_insert so the record is never created.
    """
    user = user or frappe.session.user

    # Only enforce for your IR roles
    if not _effective_ir_role(user):
        return

    designation = getattr(doc, designation_field, None)
    if not designation:
        return

    if designation in set(_restricted_designations_for_user(user)):
        frappe.throw(
            f"You are not permitted to create or edit this document for designation: {designation}",
            frappe.PermissionError,
        )


def get_ir_notification_recipients(include_owner: str | None = None):
    """
    Returns (recipient_emails_sorted, name_by_email) from IR Role Restrictions.report_recipients.

    Reads child rows directly from the DB to avoid singleton caching issues (bench console, workers).

    - Only uses enabled users.
    - Uses child row.email_address if present; otherwise falls back to User.email.
    - If include_owner is provided (e.g. doc.owner), it will be added too (if enabled).
    """
    recipient_emails = set()
    name_by_email = {}

    parent = "IR Role Restrictions"      # Single DocType name = docname
    parenttype = "IR Role Restrictions"
    parentfield = "report_recipients"

    # Pull child rows directly (fail-open: returns [] if singleton not saved yet)
    rows = frappe.get_all(
        "IR User Restriction Table",
        filters={
            "parenttype": parenttype,
            "parent": parent,
            "parentfield": parentfield,
        },
        fields=["user", "email_address"],
        order_by="idx asc",
    )

    for row in rows:
        user = row.get("user")
        email = row.get("email_address")

        if user:
            enabled, user_email, full_name = frappe.db.get_value(
                "User", user, ["enabled", "email", "full_name"]
            ) or (0, None, None)

            if not enabled:
                continue

            email = email or user_email
            if email:
                recipient_emails.add(email)
                name_by_email[email] = full_name or user

        elif email:
            # Optional: allow “email only” rows (if you ever support that)
            recipient_emails.add(email)
            name_by_email[email] = "IR Team"

    # Optionally include the doc owner
    if include_owner:
        enabled, owner_email, owner_full_name = frappe.db.get_value(
            "User", include_owner, ["enabled", "email", "full_name"]
        ) or (0, None, None)
        if enabled and owner_email:
            recipient_emails.add(owner_email)
            name_by_email[owner_email] = owner_full_name or include_owner

    return sorted(recipient_emails), name_by_email


def validate_contract_of_employment(doc, method=None):
    # Restriction field is 'designation'
    _raise_if_restricted_designation(doc, "designation")


def validate_disciplinary_action(doc, method=None):
    # Restriction field is 'accused_pos'
    _raise_if_restricted_designation(doc, "accused_pos")


def contract_of_employment_has_permission(doc, user: str | None = None, ptype: str | None = None) -> bool:
    """
    DocType: Contract of Employment
    Restriction field: designation

    This blocks opening/reading the document directly if designation is restricted.
    """
    user = user or frappe.session.user

    # Only enforce for your IR roles
    if not _effective_ir_role(user):
        return True

    # Enforce for read + other common operations (print/export/email etc.)
    if ptype in (None, "read", "create", "write", "submit", "cancel", "delete", "print", "email", "report", "export"):
        return not _is_designation_restricted_for_user(getattr(doc, "designation", None), user)

    return True

def disciplinary_action_has_permission(doc, user: str | None = None, ptype: str | None = None) -> bool:
    """
    DocType: Disciplinary Action
    Restriction field: accused_pos

    This blocks opening/reading the document directly if accused_pos is restricted.
    """
    user = user or frappe.session.user

    # Only enforce for your IR roles
    if not _effective_ir_role(user):
        return True

    # Enforce for read + other common operations (print/export/email etc.)
    # If you ONLY want to block opening, change this to: if ptype in (None, "read"):
    if ptype in (None, "read", "create", "write", "submit", "cancel", "delete", "print", "email", "report", "export"):
        return not _is_designation_restricted_for_user(getattr(doc, "accused_pos", None), user)

    return True


# --------------------------------------------------------------------
# TEMPLATE for future doctypes:
#
# def my_doctype_permission_query_conditions(user: str) -> str:
#     restricted = _restricted_designations_for_user(user)
#     if not restricted:
#         return ""
#     return _sql_not_in_designations("`tabMy DocType`.`my_designation_field`", restricted)
#
# def my_doctype_has_permission(doc, user: str | None = None, ptype: str | None = None) -> bool:
#     user = user or frappe.session.user
#     if not _effective_ir_role(user):
#         return True
#     if ptype in (None, "read", "create", "write", "submit", "cancel", "delete", "print", "email", "report", "export"):
#         return not _is_designation_restricted_for_user(getattr(doc, "my_designation_field", None), user)
#     return True
# --------------------------------------------------------------------


# --------------------------------------------------------------------
# Performance / linked outcome helpers
# Integrated from utils/performance_common.py
# --------------------------------------------------------------------

PARENT_DOCTYPE_BY_FIELD = {
    "linked_disciplinary_action": "Disciplinary Action",
    "linked_incapacity_proceeding": "Incapacity Proceedings",
    "linked_poor_performance": "Poor Performance",
}


def linked_parent(doc):
    for fieldname, doctype in PARENT_DOCTYPE_BY_FIELD.items():
        value = doc.get(fieldname)
        if value:
            return fieldname, value, doctype
    return None, None, None


def autoname_by_linked_parent(doc, prefix):
    fieldname, linked_name, _doctype = linked_parent(doc)
    if not linked_name:
        return

    existing = frappe.get_all(doc.doctype, filters={fieldname: linked_name}, fields=["name"])
    if not existing:
        doc.name = f"{prefix}-{linked_name}"
        return

    latest_revision = 0
    base = f"{prefix}-{linked_name}-"
    for row in existing:
        if (row.name or "").startswith(base):
            try:
                latest_revision = max(latest_revision, int(row.name.split("-")[-1]))
            except Exception:
                pass
    doc.name = f"{prefix}-{linked_name}-{latest_revision + 1}"


def create_manual_version(doc, fieldname, old_value, new_value):
    frappe.get_doc({
        "doctype": "Version",
        "ref_doctype": doc.doctype,
        "docname": doc.name,
        "data": frappe.as_json({"changed": [[fieldname, old_value, new_value]]}),
    }).insert(ignore_permissions=True)


def get_linked_outcome(doc_name, doctype):
    linked_doc = frappe.get_doc(doctype, doc_name)
    return {
        "linked_doc_name": linked_doc.name,
        "linked_doctype": doctype,
        "outcome": linked_doc.get("outcome"),
        "outcome_date": linked_doc.get("outcome_date"),
        "outcome_start": linked_doc.get("outcome_start"),
        "outcome_end": linked_doc.get("outcome_end"),
    }


def clear_parent_outcome(doc):
    _field, linked_name, linked_doctype = linked_parent(doc)
    if not linked_name:
        return

    linked_doc = frappe.get_doc(linked_doctype, linked_name)
    linked_doc.flags.ignore_version = True

    old = {field: linked_doc.get(field) for field in ["outcome", "outcome_date", "outcome_start", "outcome_end"]}

    if linked_doc.docstatus == 0:
        for field in old:
            linked_doc.set(field, None)
        linked_doc.save(ignore_permissions=True)
    else:
        for field in old:
            linked_doc.db_set(field, None)
            create_manual_version(linked_doc, field, old[field], None)

    frappe.msgprint(_("Outcome fields for {0} ({1}) have been cleared.").format(linked_name, linked_doctype), alert=True)


def set_parent_outcome(doc, outcome, outcome_date=None, outcome_start=None, outcome_end=None):
    _field, linked_name, linked_doctype = linked_parent(doc)
    if not linked_name:
        return

    linked_doc = frappe.get_doc(linked_doctype, linked_name)
    linked_doc.flags.ignore_version = True

    updates = {
        "outcome": outcome,
        "outcome_date": outcome_date,
        "outcome_start": outcome_start,
        "outcome_end": outcome_end,
    }
    updates = {k: v for k, v in updates.items() if v is not None}
    old = {field: linked_doc.get(field) for field in updates}

    if linked_doc.docstatus == 0:
        for field, value in updates.items():
            linked_doc.set(field, value)
        linked_doc.save(ignore_permissions=True)
    else:
        for field, value in updates.items():
            linked_doc.db_set(field, value)
            create_manual_version(linked_doc, field, old.get(field), value)

    frappe.msgprint(_("Outcome fields for {0} ({1}) have been updated.").format(linked_name, linked_doctype), alert=True)


def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value("Company", company, "default_letter_head")
    return {"letter_head": letter_head} if letter_head else {}


def fetch_employee_name(employee):
    return {"employee_name": frappe.db.get_value("Employee", employee, "employee_name") or ""}


def fetch_performance_data(poor_performance):
    if not frappe.db.exists("Poor Performance", poor_performance):
        frappe.throw(_("Poor Performance {0} not found").format(poor_performance))

    data = frappe.db.get_value(
        "Poor Performance",
        poor_performance,
        [
            "employee",
            "employee_name",
            "employee_designation",
            "company",
            "details_of_poor_performance",
            "outcome",
            "outcome_date",
        ],
        as_dict=True,
    ) or {}

    # Alias for generated action forms.
    # Action DocTypes use a generic field called performance_details.
    data["performance_details"] = data.get("details_of_poor_performance") or ""

    if data.get("outcome"):
        data["outcome_label"] = (
            frappe.db.get_value("Offence Outcome", data.get("outcome"), "disc_offence_out")
            or data.get("outcome")
        )
    else:
        data["outcome_label"] = ""

    doc = frappe.get_doc("Poor Performance", poor_performance)

    history = []
    for row in (doc.get("previous_disciplinary_outcomes") or []):
        history.append({
            "performance_action": row.get("performance_action"),
            "date": row.get("date"),
            "charges": row.get("charges"),
            "sanction": row.get("sanction"),
        })

    data.update({"previous_performance_outcomes": history})
    return data


def hydrate_employee_from_source(source, target):
    target.employee = source.get("employee")
    target.names = source.get("employee_name")
    target.coy = source.get("employee")
    target.position = source.get("employee_designation")
    target.company = source.get("company")
