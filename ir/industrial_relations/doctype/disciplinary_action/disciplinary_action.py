# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months

class DisciplinaryAction(Document):
    pass

@frappe.whitelist()
def fetch_employee_data(employee, fields):
    frappe.flags.ignore_permissions = True

    # Parse the fields argument from JSON string to dictionary
    fields = json.loads(fields)

    data = {}
    for field in fields:
        value = frappe.db.get_value('Employee', employee, field)
        data[fields[field]] = value if value else ''
    
    return data

@frappe.whitelist()
def fetch_default_letter_head(company):
    frappe.flags.ignore_permissions = True

    letter_head = frappe.db.get_value('Company', company, 'default_letter_head')
    return letter_head if letter_head else ''

@frappe.whitelist()
def fetch_disciplinary_history(accused, current_doc_name):
    frappe.flags.ignore_permissions = True

    disciplinary_actions = frappe.get_all('Disciplinary Action', filters={
        'accused': accused,
        'name': ['!=', current_doc_name]
    }, fields=['name', 'outcome_date', 'outcome'])

    history = []

    for action in disciplinary_actions:
        action_doc = frappe.get_doc('Disciplinary Action', action.name)
        charges = '\n'.join([f"({charge_row.code_item}) {charge_row.charge}" for charge_row in action_doc.final_charges])

        # Check if the outcome is linked to an "Offence Outcome" document
        if action_doc.outcome:
            offence_outcome = frappe.get_doc('Offence Outcome', action_doc.outcome)
            sanction = offence_outcome.disc_offence_out if offence_outcome else f"Pending {action_doc.name}"
        else:
            sanction = f"Pending {action_doc.name}"

        history.append({
            'disc_action': action_doc.name,
            'date': action_doc.outcome_date,
            'sanction': sanction,
            'charges': charges
        })

    return history

import frappe

@frappe.whitelist()
def get_linked_documents(disciplinary_action_name: str) -> dict:
    """Return all docs linked to this Disciplinary Action via Dynamic Links (or explicit link fields)."""
    frappe.flags.ignore_permissions = True

    # Collect dynamic link mappings (example pattern—keep your existing logic/doctype list)
    linked_info = {}

    # Example: iterate linked doctypes you already gather in your code
    linked_doctypes = [
        # ("DocType Name", "linking_field_in_that_doctype")
        # keep your existing list here
    ]

    for linked_doctype, linking_field in linked_doctypes:
        try:
            records = frappe.get_all(
                linked_doctype,
                filters={linking_field: disciplinary_action_name},
                fields=["name"],
                order_by="modified desc"   # <-- avoid inheriting unsafe defaults
            )
            linked_info[linked_doctype] = [r["name"] for r in records]
        except Exception as e:
            # Don’t blow up the whole call if one doctype misbehaves
            frappe.log_error(f"Error fetching linked docs for {linked_doctype}: {e}", "get_linked_documents")
            linked_info[linked_doctype] = []

    return linked_info

@frappe.whitelist()
def fetch_complainant_data(complainant):
    frappe.flags.ignore_permissions = True

    data = {
        'compl_name': frappe.db.get_value('Employee', complainant, 'employee_name') or '',
        'compl_pos': frappe.db.get_value('Employee', complainant, 'designation') or ''
    }
    
    return data

@frappe.whitelist()
def check_if_ss(accused):
    frappe.flags.ignore_permissions = True

    # Explicit order_by prevents inheriting unsafe ListView/DocType defaults after the Frappe upgrade
    trade_unions = frappe.get_all(
        "Trade Union",
        fields=["name"],
        order_by="name asc"
    )

    for tu in trade_unions:
        ss_list = frappe.get_all(
            "Union Shop Stewards",
            filters={"parent": tu.name, "parentfield": "ss_list", "ss_id": accused},
            fields=["ss_id"],
            order_by="modified desc"
        )
        if ss_list:
            return {"is_ss": True, "ss_union": tu.name}

    return {"is_ss": False, "ss_union": None}