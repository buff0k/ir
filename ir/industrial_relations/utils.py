# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import escape_html, get_url_to_form


def check_app_permission():
    """Control whether the IR app is shown on the Apps screen."""
    if frappe.session.user == "Administrator":
        return True

    required_roles = {
        "System Manager",
        "IR Manager",
        "IR Officer",
        "IR User",
        "Payroll Manager",
        "Payroll User",
        "HR Manager",
        "HR User",
        "Training Manager",
        "Training Facilitator",
        "Training Administrator",
    }
    return bool(required_roles.intersection(frappe.get_roles(frappe.session.user)))


def get_ir_notification_recipients(include_owner: str | None = None):
    recipient_emails = set()
    name_by_email = {}

    rows = frappe.get_all(
        "IR User Restriction Table",
        filters={
            "parent": "IR Role Restrictions",
            "parenttype": "IR Role Restrictions",
            "parentfield": "report_recipients",
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
            recipient_emails.add(email)
            name_by_email[email] = "IR Team"

    if include_owner:
        enabled, owner_email, owner_full_name = frappe.db.get_value(
            "User", include_owner, ["enabled", "email", "full_name"]
        ) or (0, None, None)
        if enabled and owner_email:
            recipient_emails.add(owner_email)
            name_by_email[owner_email] = owner_full_name or include_owner

    return sorted(recipient_emails), name_by_email


PARENT_DOCTYPE_BY_FIELD = {
    "linked_disciplinary_action": "Disciplinary Action",
    "linked_incapacity_proceeding": "Incapacity Proceedings",
    "linked_poor_performance": "Poor Performance",
}


def linked_parent(doc):
    # New generic intervention model.
    if doc.get("ir_intervention") and doc.get("linked_intervention"):
        return "linked_intervention", doc.get("linked_intervention"), doc.get("ir_intervention")

    # Legacy/action-form model.
    for fieldname, doctype in PARENT_DOCTYPE_BY_FIELD.items():
        value = doc.get(fieldname)
        if value:
            return fieldname, value, doctype
    return None, None, None


def autoname_by_linked_parent(doc, prefix):
    fieldname, linked_name, linked_doctype = linked_parent(doc)
    if not linked_name:
        return

    filters = {fieldname: linked_name}
    if fieldname == "linked_intervention" and doc.meta.has_field("ir_intervention"):
        filters["ir_intervention"] = linked_doctype

    existing = frappe.get_all(doc.doctype, filters=filters, fields=["name"])
    base_name = f"{prefix}-{linked_name}"
    if not existing:
        doc.name = base_name
        return

    latest_revision = 0
    revision_prefix = f"{base_name}-"
    for row in existing:
        if (row.name or "").startswith(revision_prefix):
            try:
                latest_revision = max(latest_revision, int(row.name.rsplit("-", 1)[-1]))
            except (TypeError, ValueError):
                pass
    doc.name = f"{base_name}-{latest_revision + 1}"


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
    fields = ["outcome", "outcome_date", "outcome_start", "outcome_end"]
    old = {field: linked_doc.get(field) for field in fields}

    if linked_doc.docstatus == 0:
        for field in fields:
            linked_doc.set(field, None)
        linked_doc.save(ignore_permissions=True)
    else:
        for field in fields:
            linked_doc.db_set(field, None)
            create_manual_version(linked_doc, field, old[field], None)

    frappe.msgprint(
        _("Outcome fields for {0} ({1}) have been cleared.").format(linked_name, linked_doctype),
        alert=True,
    )


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
    updates = {key: value for key, value in updates.items() if value is not None}
    old = {field: linked_doc.get(field) for field in updates}

    if linked_doc.docstatus == 0:
        for field, value in updates.items():
            linked_doc.set(field, value)
        linked_doc.save(ignore_permissions=True)
    else:
        for field, value in updates.items():
            linked_doc.db_set(field, value)
            create_manual_version(linked_doc, field, old.get(field), value)

    frappe.msgprint(
        _("Outcome fields for {0} ({1}) have been updated.").format(linked_name, linked_doctype),
        alert=True,
    )


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
    data["performance_details"] = data.get("details_of_poor_performance") or ""

    if data.get("outcome"):
        data["outcome_label"] = (
            frappe.db.get_value("Offence Outcome", data.get("outcome"), "disc_offence_out")
            or data.get("outcome")
        )
    else:
        data["outcome_label"] = ""

    doc = frappe.get_doc("Poor Performance", poor_performance)
    data["previous_performance_outcomes"] = [
        {
            "performance_action": row.get("performance_action"),
            "date": row.get("date"),
            "charges": row.get("charges"),
            "sanction": row.get("sanction"),
        }
        for row in (doc.get("previous_disciplinary_outcomes") or [])
    ]
    return data


ALLOWED_EMPLOYEE_FETCH_FIELDS = {
    "employee_name",
    "employee",
    "designation",
    "company",
    "date_of_joining",
    "branch",
}


def fetch_employee_fields(employee, fields):
    """Fetch a restricted set of Employee fields for populating generated-document forms.

    `fields` is a JSON-encoded (or already-decoded) mapping of source Employee
    fieldname -> target fieldname on the calling form. Only source fields in
    ALLOWED_EMPLOYEE_FETCH_FIELDS are honoured; anything else is silently dropped.
    """
    if isinstance(fields, str):
        fields = json.loads(fields)

    data = {}
    for source_field, target_field in fields.items():
        if source_field not in ALLOWED_EMPLOYEE_FETCH_FIELDS:
            continue
        data[target_field] = frappe.db.get_value("Employee", employee, source_field) or ""
    return data


def get_letter_head_string(company):
    """Return the company's default letter head as a bare string (not a dict)."""
    return fetch_company_letter_head(company).get("letter_head", "")


def fetch_complainant_fields(complainant):
    """Return an Employee's name/designation for use as a complainant, doctype-agnostic."""
    return {
        "name": frappe.db.get_value("Employee", complainant, "employee_name") or "",
        "designation": frappe.db.get_value("Employee", complainant, "designation") or "",
    }


def check_if_ss(employee):
    """Return whether `employee` is a listed Shop Steward for any Trade Union, and which one."""
    for trade_union in frappe.get_all("Trade Union", fields=["name"], order_by="name asc"):
        rows = frappe.get_all(
            "Union Shop Stewards",
            filters={"parent": trade_union.name, "parentfield": "ss_list", "ss_id": employee},
            fields=["ss_id"],
            limit_page_length=1,
        )
        if rows:
            return {"is_ss": True, "ss_union": trade_union.name}

    return {"is_ss": False, "ss_union": None}


def _linked_docs_empty_html(message):
    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__empty">{message}</div>
    </div>
    """


def render_linked_docs_html(source_name, mappings):
    """Render the shared "linked documents" card grid used by several source doctypes.

    `mappings` is a list of (label, target_doctype, backref) tuples, where `backref`
    is either a plain fieldname (filtered as {backref: source_name}), or a dict of
    extra filters combined with {"linked_intervention": source_name} for the generic
    intervention model.
    """
    if not source_name or source_name.startswith("new-"):
        return _linked_docs_empty_html("Linked documents will appear here once the record is saved.")

    cards = []
    total = 0

    for label, target_doctype, backref in mappings:
        if isinstance(backref, dict):
            filters = dict(backref)
            filters["linked_intervention"] = source_name
        else:
            filters = {backref: source_name}

        try:
            rows = frappe.get_all(
                target_doctype,
                filters=filters,
                fields=["name"],
                order_by="modified desc",
            )
        except Exception:
            frappe.log_error(
                title=f"get_linked_docs_html query failed: {target_doctype}",
                message=frappe.get_traceback(),
            )
            rows = []

        if not rows:
            continue

        total += len(rows)

        chips = []
        for row in rows:
            url = get_url_to_form(target_doctype, row.name)
            chips.append(
                f"""
                <a class="ir-linked-docs__chip"
                   href="{escape_html(url)}"
                   target="_blank"
                   rel="noopener">
                   {escape_html(row.name)}
                </a>
                """
            )

        cards.append(
            f"""
            <div class="ir-linked-docs__card">
              <div class="ir-linked-docs__card-header">
                <div class="ir-linked-docs__title">{escape_html(label)}</div>
                <div class="ir-linked-docs__badge">{len(rows)}</div>
              </div>
              <div class="ir-linked-docs__chips">
                {''.join(chips)}
              </div>
            </div>
            """
        )

    if total == 0:
        return _linked_docs_empty_html("No linked documents yet.")

    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__grid">
        {''.join(cards)}
      </div>
    </div>
    """


def _latest_work_history_row(rows):
    if not rows:
        return None
    with_from = [row for row in rows if row.get("from_date")]
    if with_from:
        return sorted(with_from, key=lambda row: row.from_date)[-1]
    return rows[-1]


def append_internal_work_history(employee, *, from_date, to_date=None, branch=None, department=None, designation=None):
    """Close the employee's current Internal Work History row (if any) and append a
    new one reflecting a branch/department/designation change effective `from_date`.

    Any of branch/department/designation left as None carries forward the latest
    existing row's value (falling back to the Employee's current field) - pass only
    the field(s) that actually changed. Does not save the Employee document; the
    caller decides when to save (e.g. batched with other field changes in the same
    .save() call).
    """
    history = employee.get("internal_work_history") or []
    latest = _latest_work_history_row(history)

    if not latest:
        prev_branch = employee.get("branch")
        prev_department = employee.get("department")
        prev_designation = employee.get("designation")
        employee.append(
            "internal_work_history",
            {
                "branch": prev_branch,
                "department": prev_department,
                "designation": prev_designation,
                "from_date": employee.get("date_of_joining"),
                "to_date": from_date,
            },
        )
    else:
        prev_branch = latest.get("branch") or employee.get("branch")
        prev_department = latest.get("department") or employee.get("department")
        prev_designation = latest.get("designation") or employee.get("designation")
        latest.to_date = from_date

    employee.append(
        "internal_work_history",
        {
            "branch": branch or prev_branch,
            "department": department or prev_department,
            "designation": designation or prev_designation,
            "from_date": from_date,
            "to_date": to_date,
        },
    )


def hydrate_employee_from_source(source, target):
    """Populate common generated-document employee fields without assuming a coy field."""
    employee = source.get("employee") or source.get("accused")
    employee_name = source.get("employee_name") or source.get("accused_name")
    position = source.get("employee_designation") or source.get("accused_pos")

    if target.meta.has_field("employee"):
        target.employee = employee
    if target.meta.has_field("names"):
        target.names = employee_name
    if target.meta.has_field("coy"):
        target.coy = employee
    if target.meta.has_field("position"):
        target.position = position
    if target.meta.has_field("company"):
        target.company = source.get("company")
