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

# Cancelling these doctypes directly (bypassing a formal Appeal) is blocked for
# everyone except System Manager. The sanctioned path is: submit an Appeal
# Against Outcome with an Upheld/Partially Upheld decision, whose on_submit
# performs the cancel+amend itself via flags.ignore_permissions - which skips
# this check entirely (frappe.has_permission short-circuits before this hook
# is even called when that flag is set).
CANCEL_RESTRICTED_DOCTYPES = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
    "Appeal Against Outcome",
}

DESIGNATION_FIELD_BY_DOCTYPE = {
    "Contract of Employment": "designation",
    "Termination Form": "requested_for_designation",
    "Status Change Form": "current_designation",
    "Site Transfer Form": "designation",
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
# Restrictions. Deliberately does not include External Dispute Resolution (no
# single branch - it's inherently multi-employee/multi-branch).
#
# NTA Enquiry and Written Outcome USED to be deliberately excluded here too
# ("no single branch"), which was wrong - both carry their own direct
# `employee` field (confirmed against live data: 307 of 333 NTA Enquiry
# records visible to a real branch-restricted user were for employees outside
# every branch she was assigned, because nothing was filtering them at all).
# This same dict also identifies "the employee this record is about" for the
# own-case exclusion below, so fixing it here closes both gaps at once.
BRANCH_LIMITED_DOCTYPES = {
    "Contract of Employment": "employee",
    "Termination Form": "requested_for",
    "Status Change Form": "employee",
    "Site Transfer Form": "employee",
    "Disciplinary Action": "accused",
    "Incapacity Proceedings": "accused",
    "Poor Performance": "employee",
    "NTA Enquiry": "employee",
    "Written Outcome": "employee",
    "Warning Form": "employee",
    "Suspension Form": "employee",
    "Dismissal Form": "employee",
    "Demotion Form": "employee",
    "Pay Deduction Form": "employee",
    "Pay Reduction Form": "employee",
    "No Further Action Form": "employee",
    "Appeal Against Outcome": "employee",
}

# The 3 source case doctypes' own Responsible IR link field. Poor Performance's
# is named "ir", not "responsible_ir" - a pre-existing naming inconsistency on
# that doctype (see also its ir_name fetch_from fix).
RESPONSIBLE_IR_FIELD_BY_DOCTYPE = {
    "Disciplinary Action": "responsible_ir",
    "Incapacity Proceedings": "responsible_ir",
    "Poor Performance": "ir",
}

# Downstream action doctypes that carry the "new generic intervention model"
# ir_intervention (source doctype name) + linked_intervention (Dynamic Link to
# the actual case) fields - i.e. everything that implements/flows from one of
# the 3 source cases above, but has no Responsible IR field of its own.
INTERVENTION_LINK_DOCTYPES = {
    "NTA Enquiry",
    "Written Outcome",
    "Warning Form",
    "Suspension Form",
    "Dismissal Form",
    "Demotion Form",
    "Pay Deduction Form",
    "Pay Reduction Form",
    "No Further Action Form",
    "Appeal Against Outcome",
}

# The 3 doctypes a disciplinary/incapacity/performance matter actually starts
# as. Own-case exclusion (see _is_own_case) applies only to these - an
# employee who also holds an IR role must never see their own case being
# investigated, but IS allowed to see their own already-Submitted outcome
# documents (Warning Form, Suspension Form, ...) once the case concludes,
# same as any other employee whose case that outcome concerns.
ROOT_CASE_DOCTYPES = (
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
)

# Doctypes where IR User is restricted to Submitted (docstatus=1) records only
# - Contract of Employment (read-only for IR User in the doctype JSON) plus
# every case/outcome doctype (all gated by a Responsible IR override that lets
# the person actually assigned to a case see their own Draft regardless).
# Deliberately excludes Termination Form/Status Change Form/Site Transfer Form
# below - IR User genuinely has create/write on those three with no
# Responsible IR concept at all, so this rule would otherwise lock a creator
# out of their own just-drafted record with no escape hatch.
IR_USER_SUBMITTED_ONLY_DOCTYPES = {"Contract of Employment", *ROOT_CASE_DOCTYPES, *INTERVENTION_LINK_DOCTYPES}


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
    fallback, per design.

    Doctype-eligibility (whether branch limits apply to a given doctype at all) is
    the caller's responsibility - existing callers only reach this function via
    BRANCH_LIMITED_DOCTYPES.get(doctype) truthiness checks already, so nothing here
    depends on that dict directly. This lets ad-hoc callers (e.g. weekly report
    filtering via passes_limits) check any doctype/employee pair without needing to
    register it there too, without changing anything for existing callers."""
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


def _sql_root_case_ok_subquery(root_doctype: str, user: str | None) -> str:
    """SELECT name FROM tab{root_doctype} WHERE <passes Designation/Branch
    Limits for `user`> - the building block _sql_outcome_root_restriction
    below joins a downstream outcome doctype against, per possible root."""
    conditions = []
    restricted = restricted_designations_for_user(user)
    if restricted:
        designation_field = DESIGNATION_FIELD_BY_DOCTYPE[root_doctype]
        conditions.append(_sql_not_in_designations(f"`{designation_field}`", restricted))
    branches = responsible_branches_for_user(user)
    if branches:
        employee_field = BRANCH_LIMITED_DOCTYPES[root_doctype]
        escaped = ", ".join(frappe.db.escape(value) for value in branches)
        conditions.append(f"`{employee_field}` IN (SELECT name FROM `tabEmployee` WHERE branch IN ({escaped}))")
    where = " and ".join(conditions) if conditions else "1=1"
    return f"SELECT name FROM `tab{root_doctype}` WHERE {where}"


def _sql_outcome_root_restriction(doctype: str, user: str | None) -> str | None:
    """Designation/Branch Limits for a downstream outcome/action doctype
    (INTERVENTION_LINK_DOCTYPES), evaluated against the ROOT case it traces
    back to via ir_intervention/linked_intervention rather than the outcome's
    own (separately populated, and not necessarily kept in sync) copy of
    employee/position - i.e. if the root Disciplinary Action is restricted for
    this user, every Warning Form/NTA Enquiry/... under it is too. Does NOT
    include own-case exclusion - see ROOT_CASE_DOCTYPES."""
    if not (restricted_designations_for_user(user) or responsible_branches_for_user(user)):
        return None

    clauses = [
        f"(`tab{doctype}`.`ir_intervention` = {frappe.db.escape(root_doctype)} "
        f"and `tab{doctype}`.`linked_intervention` in ({_sql_root_case_ok_subquery(root_doctype, user)}))"
        for root_doctype in ROOT_CASE_DOCTYPES
    ]
    return "(" + " or ".join(clauses) + ")"


def _root_case_fields(doc) -> tuple[str | None, str | None]:
    """(employee, designation) `doc`'s Branch/Designation restriction should be
    evaluated against. For a downstream outcome/action doctype
    (INTERVENTION_LINK_DOCTYPES), that's the ROOT case it traces back to via
    ir_intervention/linked_intervention (document-level counterpart to
    _sql_outcome_root_restriction) - for anything else (the 3 root case
    doctypes themselves, and doctypes with no intervention concept at all
    like Contract of Employment), it's the doc's own fields, unchanged from
    before this existed."""
    if doc.doctype in INTERVENTION_LINK_DOCTYPES:
        root_doctype = doc.get("ir_intervention")
        root_name = doc.get("linked_intervention")
        if root_doctype not in ROOT_CASE_DOCTYPES or not root_name:
            return None, None
        employee_field = BRANCH_LIMITED_DOCTYPES[root_doctype]
        designation_field = DESIGNATION_FIELD_BY_DOCTYPE[root_doctype]
        row = frappe.db.get_value(root_doctype, root_name, [employee_field, designation_field], as_dict=True)
        if not row:
            return None, None
        return row.get(employee_field), row.get(designation_field)

    employee_field = BRANCH_LIMITED_DOCTYPES.get(doc.doctype)
    designation_field = DESIGNATION_FIELD_BY_DOCTYPE.get(doc.doctype)
    employee = doc.get(employee_field) if employee_field else None
    designation = doc.get(designation_field) if designation_field else None
    return employee, designation


def _own_employee(user: str | None = None) -> str | None:
    """The Employee record (if any) linked to `user`'s own login."""
    user = user or frappe.session.user
    if not user:
        return None
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _is_own_case(doc, user: str | None = None) -> bool:
    """True if `doc` is about the viewing user's own Employee record - e.g. a
    Disciplinary Action where they themselves are the accused. Confirmed live:
    an IR User with real Branch Limits could see her own 3 Disciplinary Action
    records (one still a Draft) purely because her own Employee record happens
    to sit inside a branch she's responsible for. Nobody should be able to
    browse their own case file through general IR/Branch-scoped access -
    that's an identity check, unrelated to org-structure scoping, and takes
    priority over everything else including the Responsible IR override (a
    person can't legitimately be the impartial Responsible IR on their own
    case)."""
    employee_field = BRANCH_LIMITED_DOCTYPES.get(doc.doctype)
    if not employee_field:
        return False
    own_employee = _own_employee(user)
    if not own_employee:
        return False
    return doc.get(employee_field) == own_employee


def _sql_own_case_exclusion(doctype: str, user: str | None) -> str | None:
    """SQL counterpart to _is_own_case, for list queries."""
    employee_field = BRANCH_LIMITED_DOCTYPES.get(doctype)
    if not employee_field:
        return None
    own_employee = _own_employee(user)
    if not own_employee:
        return None
    return f"`tab{doctype}`.`{employee_field}` != {frappe.db.escape(own_employee)}"


def _sql_responsible_ir_override(doctype: str, user: str | None) -> str | None:
    """SQL condition matching records where `user` is the effective Responsible
    IR - the person actually assigned to implement this case - so Designation
    Limits and Branch Limits (both inherited from the IR Role Restrictions
    singleton) never stand between them and their own case. Directly on the 3
    source case doctypes via their own Responsible IR field; on a downstream
    action doctype (NTA Enquiry, Written Outcome, a sanction form, Appeal
    Against Outcome) via the case it traces back to through
    ir_intervention/linked_intervention - they're "the person implementing
    the action" too, just one step removed from the source case."""
    if not user:
        return None

    field = RESPONSIBLE_IR_FIELD_BY_DOCTYPE.get(doctype)
    if field:
        return f"`tab{doctype}`.`{field}` = {frappe.db.escape(user)}"

    if doctype in INTERVENTION_LINK_DOCTYPES:
        clauses = [
            f"(`tab{doctype}`.`ir_intervention` = {frappe.db.escape(source_doctype)} "
            f"and `tab{doctype}`.`linked_intervention` in "
            f"(select name from `tab{source_doctype}` where `{source_field}` = {frappe.db.escape(user)}))"
            for source_doctype, source_field in RESPONSIBLE_IR_FIELD_BY_DOCTYPE.items()
        ]
        return "(" + " or ".join(clauses) + ")"

    return None


def _is_effective_responsible_ir(doc, user: str | None) -> bool:
    """Document-level counterpart to _sql_responsible_ir_override, for a single
    already-loaded doc (has_permission/validate hooks) rather than a list query."""
    if not user:
        return False

    field = RESPONSIBLE_IR_FIELD_BY_DOCTYPE.get(doc.doctype)
    if field:
        return doc.get(field) == user

    if doc.doctype in INTERVENTION_LINK_DOCTYPES:
        source_doctype = doc.get("ir_intervention")
        linked_name = doc.get("linked_intervention")
        source_field = RESPONSIBLE_IR_FIELD_BY_DOCTYPE.get(source_doctype)
        if source_doctype and linked_name and source_field:
            return frappe.db.get_value(source_doctype, linked_name, source_field) == user

    return False


def _permission_query(doctype: str, user: str | None) -> str:
    conditions = []

    if doctype in INTERVENTION_LINK_DOCTYPES:
        # Designation/Branch Limits inherited from the root case (see
        # _sql_outcome_root_restriction) rather than evaluated on this
        # doctype's own employee/position fields.
        root_condition = _sql_outcome_root_restriction(doctype, user)
        if root_condition:
            conditions.append(root_condition)
    else:
        restricted = restricted_designations_for_user(user)
        if restricted:
            fieldname = DESIGNATION_FIELD_BY_DOCTYPE[doctype]
            conditions.append(_sql_not_in_designations(f"`tab{doctype}`.`{fieldname}`", restricted))

        employee_field = BRANCH_LIMITED_DOCTYPES.get(doctype)
        if employee_field:
            branch_condition = _sql_branch_condition(doctype, employee_field, user)
            if branch_condition:
                conditions.append(branch_condition)

    # IR User is a view-only role by design on these doctypes - see
    # IR_USER_SUBMITTED_ONLY_DOCTYPES. Folded into the same "base" conditions
    # as Designation/Branch Limits, so the Responsible IR override below (who
    # legitimately needs to see their own assigned case's drafts) still
    # bypasses it, same as it already bypasses those two.
    if effective_ir_role(user) == "IR User" and doctype in IR_USER_SUBMITTED_ONLY_DOCTYPES:
        conditions.append(f"`tab{doctype}`.`docstatus` = 1")

    base = " and ".join(conditions)

    # The Responsible IR override only matters as an escape hatch FROM an
    # active restriction - if `base` is empty there is no restriction to
    # begin with (this user has no Designation/Branch Limits configured, or
    # isn't an IR User), so the whole doctype is already unrestricted for
    # them and override must not be turned into the ONLY visible slice.
    # (Bug found live: an IR Manager with zero configured restrictions saw
    # only their own 22 of 1040 Disciplinary Action records, because
    # `override or base` picked the override on its own whenever base was
    # falsy, instead of leaving the query unrestricted.)
    override = _sql_responsible_ir_override(doctype, user)
    if base:
        combined = f"(({base}) or {override})" if override else base
    else:
        combined = ""

    # Own-case exclusion applies only to the 3 root case doctypes - an
    # employee is deliberately still allowed to see their own already-
    # Submitted outcome documents once a case concludes (ROOT_CASE_DOCTYPES).
    # ANDed around the whole thing, including the Responsible IR override -
    # nobody sees their own root case via this model, full stop.
    if doctype not in ROOT_CASE_DOCTYPES:
        return combined

    own_case_exclusion = _sql_own_case_exclusion(doctype, user)
    if own_case_exclusion and combined:
        return f"({combined}) and {own_case_exclusion}"
    return own_case_exclusion or combined


def _designation_is_restricted(designation: str | None, user: str | None = None) -> bool:
    return bool(designation) and designation in set(restricted_designations_for_user(user))


def _has_permission(doc, user: str | None = None, ptype: str | None = None) -> bool:
    user = user or frappe.session.user
    if (
        ptype == "cancel"
        and doc.doctype in CANCEL_RESTRICTED_DOCTYPES
        and "System Manager" not in frappe.get_roles(user)
    ):
        return False
    if not effective_ir_role(user):
        return True
    if ptype not in PROTECTED_PERMISSION_TYPES:
        return True
    # Own-case exclusion applies only to the 3 root case doctypes - see
    # ROOT_CASE_DOCTYPES for why outcome documents are deliberately exempt.
    if doc.doctype in ROOT_CASE_DOCTYPES and _is_own_case(doc, user):
        return False
    if _is_effective_responsible_ir(doc, user):
        return True

    employee, designation = _root_case_fields(doc)
    if _designation_is_restricted(designation, user):
        return False
    if employee and _branch_is_restricted(doc.doctype, employee, user):
        return False

    if (
        effective_ir_role(user) == "IR User"
        and doc.doctype in IR_USER_SUBMITTED_ONLY_DOCTYPES
        and doc.get("docstatus") != 1
    ):
        return False

    return True


def _validate_designation(doc, user: str | None = None) -> None:
    user = user or frappe.session.user
    if not effective_ir_role(user):
        return
    if doc.doctype in ROOT_CASE_DOCTYPES and _is_own_case(doc, user):
        frappe.throw(
            _("You cannot create or edit this document - it concerns your own record."),
            frappe.PermissionError,
        )
    if _is_effective_responsible_ir(doc, user):
        return
    _employee, designation = _root_case_fields(doc)
    if _designation_is_restricted(designation, user):
        frappe.throw(
            _("You are not permitted to create or edit this document for designation: {0}").format(designation),
            frappe.PermissionError,
        )


def passes_limits(doctype: str, user: str | None, *, designation: str | None = None, employee: str | None = None) -> bool:
    """Whether `user` would be permitted to view a `doctype` record with this
    designation/employee, combining Designation Limits and Branch Limits. Takes
    explicit values rather than a live Document, so it works equally well for a
    plain dict/frappe._dict row (e.g. from a weekly report query) as for a real
    Document. Pass `designation=None`/`employee=None` to skip that dimension
    entirely (e.g. a doctype with no meaningful single employee/branch)."""
    if not user or not effective_ir_role(user):
        return True
    if designation is not None and _designation_is_restricted(designation, user):
        return False
    if employee is not None and _branch_is_restricted(doctype, employee, user):
        return False
    return True


def recipient_passes_restrictions(doc, user: str | None) -> bool:
    """Whether `user` would be permitted to view `doc`, combining Designation Limits
    and Branch Limits (where applicable). Used to decide whether to include `user` as
    a notification recipient - the same filtering that gates record visibility."""
    designation_field = DESIGNATION_FIELD_BY_DOCTYPE.get(doc.doctype)
    employee_field = BRANCH_LIMITED_DOCTYPES.get(doc.doctype)
    return passes_limits(
        doc.doctype,
        user,
        designation=doc.get(designation_field) if designation_field else None,
        employee=doc.get(employee_field) if employee_field else None,
    )


# Permission query hooks

def contract_of_employment_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Contract of Employment", user)


def termination_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Termination Form", user)


def status_change_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Status Change Form", user)


def site_transfer_form_permission_query_conditions(user: str | None = None) -> str:
    return _permission_query("Site Transfer Form", user)


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
    return _has_permission(doc, user, ptype)


def termination_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def status_change_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def site_transfer_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def disciplinary_action_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def incapacity_proceedings_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def poor_performance_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def nta_enquiry_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def written_outcome_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def warning_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def suspension_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def dismissal_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def demotion_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def pay_deduction_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def pay_reduction_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def no_further_action_form_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


def appeal_against_outcome_has_permission(doc, user=None, ptype=None) -> bool:
    return _has_permission(doc, user, ptype)


# Validation hooks

def validate_contract_of_employment(doc, method=None):
    _validate_designation(doc)


def validate_termination_form(doc, method=None):
    _validate_designation(doc)


def validate_status_change_form(doc, method=None):
    _validate_designation(doc)


def validate_site_transfer_form(doc, method=None):
    _validate_designation(doc)


def validate_disciplinary_action(doc, method=None):
    _validate_designation(doc)


def validate_incapacity_proceedings(doc, method=None):
    _validate_designation(doc)


def validate_poor_performance(doc, method=None):
    _validate_designation(doc)


def validate_nta_enquiry(doc, method=None):
    _validate_designation(doc)


def validate_written_outcome(doc, method=None):
    _validate_designation(doc)


def validate_warning_form(doc, method=None):
    _validate_designation(doc)


def validate_suspension_form(doc, method=None):
    _validate_designation(doc)


def validate_dismissal_form(doc, method=None):
    _validate_designation(doc)


def validate_demotion_form(doc, method=None):
    _validate_designation(doc)


def validate_pay_deduction_form(doc, method=None):
    _validate_designation(doc)


def validate_pay_reduction_form(doc, method=None):
    _validate_designation(doc)


def validate_no_further_action_form(doc, method=None):
    _validate_designation(doc)


def validate_appeal_against_outcome(doc, method=None):
    _validate_designation(doc)
