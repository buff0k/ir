# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def check_app_permission():
    """Check if the user has permission to access the app (for showing it on the app screen)"""
    # Administrator always has access
    if frappe.session.user == "Administrator":
        return True

    # Check if the user has any of the required roles
    required_roles = ["System Manager", "IR Manager", "IR User", "Payroll Manager", "Payroll User", "HR Manager", "HR User", "IR Officer", "Training Manager", "Training Facilitator", "Training Administrator"]
    user_roles = frappe.get_roles(frappe.session.user)

    # Grant access if the user has at least one of the required roles
    if any(role in user_roles for role in required_roles):
        return True

    return False


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
    Reads from the singleton 'IR Role Restrictions'.

    Single fields (child tables) expected on the singleton:
      - ir_manager_restrictions
      - ir_officer_restrictions
      - ir_user_restrictions
    Each child row has: designation (Link to Designation)
    """
    user = user or frappe.session.user

    # Only apply to your three IR roles. Everyone else unaffected.
    role = _effective_ir_role(user)
    if not role:
        return []

    # Fail open if the singleton doesn't exist yet (avoid breaking system).
    try:
        doc = frappe.get_single("IR Role Restrictions")
    except Exception:
        return []

    table_field = {
        "IR Manager": "ir_manager_restrictions",
        "IR Officer": "ir_officer_restrictions",
        "IR User": "ir_user_restrictions",
    }[role]

    rows = doc.get(table_field) or []
    return [r.designation for r in rows if getattr(r, "designation", None)]

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
# TEMPLATE for future doctypes:
#
# def my_doctype_permission_query_conditions(user: str) -> str:
#     restricted = _restricted_designations_for_user(user)
#     if not restricted:
#         return ""
#     return _sql_not_in_designations("`tabMy DocType`.`my_designation_field`", restricted)
# --------------------------------------------------------------------