# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _


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
