# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document
from frappe.utils import escape_html, get_url_to_form


class PoorPerformance(Document):
    pass


@frappe.whitelist()
def fetch_employee_data(employee, fields):
    frappe.flags.ignore_permissions = True
    fields = json.loads(fields) if isinstance(fields, str) else fields

    data = {}
    for source_field, target_field in fields.items():
        data[target_field] = frappe.db.get_value("Employee", employee, source_field) or ""
    return data


@frappe.whitelist()
def fetch_default_letter_head(company):
    frappe.flags.ignore_permissions = True
    return frappe.db.get_value("Company", company, "default_letter_head") or ""


@frappe.whitelist()
def fetch_complainant_data(complainant):
    frappe.flags.ignore_permissions = True
    return {
        "complainant_name": frappe.db.get_value("Employee", complainant, "employee_name") or "",
        "complainant_designation": frappe.db.get_value("Employee", complainant, "designation") or "",
    }


@frappe.whitelist()
def check_if_ss(employee):
    frappe.flags.ignore_permissions = True

    for tu in frappe.get_all("Trade Union", fields=["name"], order_by="name asc"):
        rows = frappe.get_all(
            "Union Shop Stewards",
            filters={"parent": tu.name, "parentfield": "ss_list", "ss_id": employee},
            fields=["ss_id"],
            limit_page_length=1,
        )
        if rows:
            return {"is_ss": True, "ss_union": tu.name}

    return {"is_ss": False, "ss_union": None}


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
        ("NTA Enquiries", "NTA Enquiry", "linked_intervention"),
        ("Written Outcomes", "Written Outcome", "linked_intervention"),
        ("Warnings", "Warning Form", "linked_poor_performance"),
        ("No Further Action Forms", "No Further Action Form", "linked_intervention"),
        ("Dismissals", "Dismissal Form", "linked_poor_performance"),
        ("Voluntary Separations", "Voluntary Seperation Agreement", "linked_poor_performance"),
        ("Hearing Cancellations", "Hearing Cancellation Form", "linked_poor_performance"),
        ("Appeals", "Appeal Against Outcome", "linked_poor_performance"),
    ]


@frappe.whitelist()
def get_linked_docs_html(poor_performance_name):
    if not poor_performance_name or poor_performance_name.startswith("new-"):
        return """
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">Linked documents will appear here once the record is saved.</div>
        </div>
        """

    cards = []
    total = 0

    for label, target_dt, backref in _linked_doc_mappings():
        filters = {backref: poor_performance_name}
        if target_dt in ("NTA Enquiry", "Written Outcome", "No Further Action Form"):
            filters = {
                "ir_intervention": "Poor Performance",
                "linked_intervention": poor_performance_name,
            }

        try:
            rows = frappe.get_all(target_dt, filters=filters, fields=["name"], order_by="modified desc")
        except Exception:
            frappe.log_error(title="Poor Performance linked docs query failed", message=frappe.get_traceback())
            rows = []

        if not rows:
            continue

        total += len(rows)
        chips = []
        for r in rows:
            url = get_url_to_form(target_dt, r.name)
            chips.append(f"""
                <a class="ir-linked-docs__chip" href="{escape_html(url)}" target="_blank" rel="noopener">
                    {escape_html(r.name)}
                </a>
            """)

        cards.append(f"""
            <div class="ir-linked-docs__card">
              <div class="ir-linked-docs__card-header">
                <div class="ir-linked-docs__title">{escape_html(label)}</div>
                <div class="ir-linked-docs__badge">{len(rows)}</div>
              </div>
              <div class="ir-linked-docs__chips">{''.join(chips)}</div>
            </div>
        """)

    if total == 0:
        return """
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">No linked documents yet.</div>
        </div>
        """

    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__grid">{''.join(cards)}</div>
    </div>
    """
