# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import escape_html, get_url_to_form


class IncapacityProceedings(Document):
    pass


@frappe.whitelist()
def fetch_employee_data(employee, fields):
    frappe.flags.ignore_permissions = True

    fields = json.loads(fields)
    data = {}

    for field in fields:
        value = frappe.db.get_value("Employee", employee, field)
        data[fields[field]] = value if value else ""

    return data


@frappe.whitelist()
def fetch_default_letter_head(company):
    """
    Must return a STRING (client expects res.message to be the letter head string)
    """
    frappe.flags.ignore_permissions = True
    letter_head = frappe.db.get_value("Company", company, "default_letter_head")
    return letter_head if letter_head else ""


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
    frappe.flags.ignore_permissions = True
    return {
        "compl_name": frappe.db.get_value("Employee", complainant, "employee_name") or "",
        "compl_pos": frappe.db.get_value("Employee", complainant, "designation") or "",
    }


@frappe.whitelist()
def check_if_ss(accused):
    frappe.flags.ignore_permissions = True

    trade_unions = frappe.get_all("Trade Union", fields=["name"], order_by="name asc")

    for tu in trade_unions:
        ss_list = frappe.get_all(
            "Union Shop Stewards",
            filters={"parent": tu.name, "parentfield": "ss_list", "ss_id": accused},
            fields=["ss_id"],
            order_by="modified desc",
        )
        if ss_list:
            return {"is_ss": True, "ss_union": tu.name}

    return {"is_ss": False, "ss_union": None}


# --------------------------------------------------------------------------------------
# NEW: Linked documents rendered into a single HTML field "linked_docs"
# --------------------------------------------------------------------------------------

def _linked_doc_mappings():
    """
    label: Display label for the card
    target_doctype: DocType to list documents from
    backref_field: field in target_doctype that points to this Incapacity Proceeding
    """
    return [
        ("NTA Hearings", "NTA Hearing", "linked_incapacity_proceeding"),

        # You already used this linkage in your JS:
        ("Written Outcomes", "Written Outcome", "linked_intervention"),

        # You have a button that creates an outcome report; include it in the linked docs view.
        ("Incapacity Outcome Reports", "Disciplinary Outcome Report", "linked_incapacity_proceeding"),

        ("Dismissals", "Dismissal Form", "linked_incapacity_proceeding"),
        ("Demotions", "Demotion Form", "linked_incapacity_proceeding"),
        ("Pay Reductions", "Pay Reduction Form", "linked_incapacity_proceeding"),
        ("Not Incapacitated Outcomes", "Not Guilty Form", "linked_incapacity_proceeding"),
        ("Suspensions", "Suspension Form", "linked_incapacity_proceeding"),
        ("Voluntary Separations", "Voluntary Seperation Agreement", "linked_incapacity_proceeding"),
        ("Hearing Cancellations", "Hearing Cancellation Form", "linked_incapacity_proceeding"),
        ("Appeals", "Appeal Against Outcome", "linked_incapacity_proceeding"),
    ]


@frappe.whitelist()
def get_linked_docs_html(incapacity_proceedings_name: str) -> str:
    """
    Returns HTML to render inside HTML field `linked_docs`.
    Uses get_url_to_form so routes never break.
    """
    if not incapacity_proceedings_name or incapacity_proceedings_name.startswith("new-"):
        return """
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">
            Linked documents will appear here once the record is saved.
          </div>
        </div>
        """

    cards = []
    total = 0

    for label, target_dt, backref in _linked_doc_mappings():
        try:
            rows = frappe.get_all(
                target_dt,
                filters={backref: incapacity_proceedings_name},
                fields=["name"],
                order_by="modified desc",
            )
        except Exception:
            frappe.log_error(
                title="get_linked_docs_html query failed",
                message=frappe.get_traceback(),
            )
            rows = []

        if not rows:
            continue

        total += len(rows)

        chips = []
        for r in rows:
            url = get_url_to_form(target_dt, r.name)
            chips.append(
                f"""
                <a class="ir-linked-docs__chip"
                   href="{escape_html(url)}"
                   target="_blank"
                   rel="noopener">
                   {escape_html(r.name)}
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
        return """
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">No linked documents yet.</div>
        </div>
        """

    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__grid">
        {''.join(cards)}
      </div>
    </div>
    """
