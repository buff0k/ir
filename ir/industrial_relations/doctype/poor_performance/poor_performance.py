# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from ir.industrial_relations import utils


class PoorPerformance(Document):
    pass


@frappe.whitelist()
def fetch_employee_data(employee, fields):
    return utils.fetch_employee_fields(employee, fields)


@frappe.whitelist()
def fetch_default_letter_head(company):
    return utils.get_letter_head_string(company)


@frappe.whitelist()
def fetch_complainant_data(complainant):
    data = utils.fetch_complainant_fields(complainant)
    return {"complainant_name": data["name"], "complainant_designation": data["designation"]}


@frappe.whitelist()
def check_if_ss(employee):
    return utils.check_if_ss(employee)


def _performance_history_row(doc):
    return {
        "performance_action": doc.name,
        "date": doc.outcome_date,
        "charges": doc.details_of_poor_performance or "",
        "sanction": _outcome_display(doc.outcome) if doc.outcome else f"Pending {doc.name}",
    }


def _outcome_display(outcome_name):
    if not outcome_name:
        return ""
    try:
        return frappe.db.get_value("Offence Outcome", outcome_name, "disc_offence_out") or outcome_name
    except Exception:
        return outcome_name


@frappe.whitelist()
def fetch_performance_history(employee, current_doc_name=None):
    """Return only Poor Performance history. This intentionally does not read Disciplinary Action."""
    frappe.flags.ignore_permissions = True

    if not employee:
        return []

    filters = {"employee": employee}
    if current_doc_name:
        filters["name"] = ["!=", current_doc_name]

    rows = frappe.get_all(
        "Poor Performance",
        filters=filters,
        fields=["name"],
        order_by="outcome_date desc, modified desc",
    )

    history = []
    for row in rows:
        try:
            doc = frappe.get_doc("Poor Performance", row.name)
            history.append(_performance_history_row(doc))
        except Exception:
            frappe.log_error(title="Poor Performance history row failed", message=frappe.get_traceback())

    return history


def _linked_doc_mappings():
    return [
        (
            "NTA Enquiries",
            "NTA Enquiry",
            {
                "ir_intervention": "Poor Performance",
                "linked_intervention": None,
            },
        ),
        (
            "Written Outcomes",
            "Written Outcome",
            {
                "ir_intervention": "Poor Performance",
                "linked_intervention": None,
            },
        ),
        (
            "Warnings",
            "Warning Form",
            {
                "ir_intervention": "Poor Performance",
                "linked_intervention": None,
            },
        ),
        (
            "No Further Action Forms",
            "No Further Action Form",
            {
                "ir_intervention": "Poor Performance",
                "linked_intervention": None,
            },
        ),
        (
            "Dismissals",
            "Dismissal Form",
            "linked_poor_performance",
        ),
        (
            "Voluntary Separations",
            "Voluntary Seperation Agreement",
            "linked_poor_performance",
        ),
        (
            "Hearing Cancellations",
            "Hearing Cancellation Form",
            "linked_poor_performance",
        ),
        (
            "Appeals",
            "Appeal Against Outcome",
            "linked_poor_performance",
        ),
    ]


@frappe.whitelist()
def get_linked_docs_html(poor_performance_name):
    return utils.render_linked_docs_html(poor_performance_name, _linked_doc_mappings())