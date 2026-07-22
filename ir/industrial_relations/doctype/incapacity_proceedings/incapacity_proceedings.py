# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from ir.industrial_relations import utils


class IncapacityProceedings(Document):
    pass


@frappe.whitelist()
def fetch_employee_data(employee, fields):
    return utils.fetch_employee_fields(employee, fields)


@frappe.whitelist()
def fetch_default_letter_head(company):
    """
    Must return a STRING (client expects res.message to be the letter head string)
    """
    return utils.get_letter_head_string(company)


@frappe.whitelist()
def fetch_incapacity_history(accused, current_doc_name):
    frappe.flags.ignore_permissions = True

    incapacity_actions = frappe.get_all(
        "Incapacity Proceedings",
        filters={"accused": accused, "name": ["!=", current_doc_name]},
        fields=["name", "outcome_date", "outcome"],
    )

    history = []

    for action in incapacity_actions:
        action_doc = frappe.get_doc("Incapacity Proceedings", action.name)

        if action_doc.outcome:
            offence_outcome = frappe.get_doc("Offence Outcome", action_doc.outcome)
            sanction = (
                offence_outcome.disc_offence_out
                if offence_outcome
                else f"Pending {action_doc.name}"
            )
        else:
            sanction = f"Pending {action_doc.name}"

        history.append(
            {
                "incap_proc": action_doc.name,
                "date": action_doc.outcome_date,
                "sanction": sanction,
                "incap_details": action_doc.details_of_incapacity,
            }
        )

    return history


@frappe.whitelist()
def get_linked_documents(incapacity_proceeding_name, linked_doctype, linking_field):
    """
    Legacy endpoint retained for backward compatibility with any other callers.
    """
    frappe.flags.ignore_permissions = True

    try:
        linked_docs = frappe.get_all(
            linked_doctype,
            filters={linking_field: incapacity_proceeding_name},
            fields=["name"],
            order_by="modified desc",
        )
        return [doc.name for doc in linked_docs]
    except Exception:
        frappe.log_error(title="get_linked_documents error", message=frappe.get_traceback())
        return []


@frappe.whitelist()
def fetch_complainant_data(complainant):
    data = utils.fetch_complainant_fields(complainant)
    return {"compl_name": data["name"], "compl_pos": data["designation"]}


@frappe.whitelist()
def check_if_ss(accused):
    return utils.check_if_ss(accused)


def _linked_doc_mappings():
    return [
        (
            "NTA Enquiries",
            "NTA Enquiry",
            {
                "ir_intervention": "Incapacity Proceedings",
                "linked_intervention": None,
            },
        ),
        (
            "Written Outcomes",
            "Written Outcome",
            {
                "ir_intervention": "Incapacity Proceedings",
                "linked_intervention": None,
            },
        ),
        ("Dismissals", "Dismissal Form", "linked_incapacity_proceeding"),
        ("Demotions", "Demotion Form", "linked_incapacity_proceeding"),
        ("Pay Reductions", "Pay Reduction Form", "linked_incapacity_proceeding"),
        (
            "No Further Action Forms",
            "No Further Action Form",
            {
                "ir_intervention": "Incapacity Proceedings",
                "linked_intervention": None,
            },
        ),
        ("Suspensions", "Suspension Form", "linked_incapacity_proceeding"),
        (
            "Voluntary Separations",
            "Voluntary Seperation Agreement",
            "linked_incapacity_proceeding",
        ),
        ("Appeals", "Appeal Against Outcome", "linked_incapacity_proceeding"),
    ]


@frappe.whitelist()
def get_linked_docs_html(incapacity_proceedings_name: str) -> str:
    """
    Returns HTML to render inside HTML field `linked_docs`.
    Uses get_url_to_form so routes never break.
    """
    return utils.render_linked_docs_html(incapacity_proceedings_name, _linked_doc_mappings())
