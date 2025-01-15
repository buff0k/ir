# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months

class IncapacityProceedings(Document):
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
def fetch_incapacity_history(accused, current_doc_name):
    frappe.flags.ignore_permissions = True

    incapacity_actions = frappe.get_all('Incapacity Proceedings', filters={
        'accused': accused,
        'name': ['!=', current_doc_name]
    }, fields=['name', 'outcome_date', 'outcome'])

    history = []

    for action in incapacity_actions:
        action_doc = frappe.get_doc('Incapacity Proceedings', action.name)
        sanction = action_doc.outcome if action_doc.outcome else f"Pending {action_doc.name}"

        # Check if the outcome is linked to an "Offence Outcome" document
        if action_doc.outcome:
            offence_outcome = frappe.get_doc('Offence Outcome', action_doc.outcome)
            sanction = offence_outcome.disc_offence_out if offence_outcome else f"Pending {action_doc.name}"
        else:
            sanction = f"Pending {action_doc.name}"

        history.append({
            'incap_proc': action_doc.name,
            'date': action_doc.outcome_date,
            'sanction': sanction,
            'incap_details': action_doc.details_of_incapacity
        })

    return history

@frappe.whitelist()
def fetch_linked_documents(doc_name):
    frappe.flags.ignore_permissions = True

    # Map Table Multiselect fields to their respective linked Doctypes
    linked_tables = {
        "linked_nta": {"doctype": "NTA Hearing", "child_table_field": "linked_nta"},
        "linked_outcome": {"doctype": "Disciplinary Outcome Report", "child_table_field": "linked_outcome"},
        "linked_dismissal": {"doctype": "Dismissal Form", "child_table_field": "linked_dismissal"},
        "linked_demotion": {"doctype": "Demotion Form", "child_table_field": "linked_demotion"},
        "linked_pay_reduction": {"doctype": "Pay Reduction Form", "child_table_field": "linked_pay_reduction"},
        "linked_not_guilty": {"doctype": "Not Guilty Form", "child_table_field": "linked_not_guilty"},
        "linked_suspension": {"doctype": "Suspension Form", "child_table_field": "linked_suspension"},
        "linked_vsp": {"doctype": "Voluntary Seperation Agreement", "child_table_field": "linked_vsp"},
        "linked_cancellation": {"doctype": "Hearing Cancellation Form", "child_table_field": "linked_cancellation"},
        "linked_appeal": {"doctype": "Appeal Against Outcome", "child_table_field": "linked_appeal"}
    }

    # Get the Incapacity Proceedings document
    incapacity_doc = frappe.get_doc("Incapacity Proceedings", doc_name)

    # Allow updates to submitted documents without validation errors
    incapacity_doc.flags.ignore_validate_update_after_submit = True

    updated = False

    for child_field, table_info in linked_tables.items():
        linked_docs = frappe.get_all(
            table_info["doctype"],
            filters={"linked_incapacity_proceeding": doc_name},
            fields=["name"]
        )

        existing_entries = {row.get(table_info["child_table_field"]) for row in incapacity_doc.get(child_field)}

        for linked_doc in linked_docs:
            if linked_doc["name"] not in existing_entries:
                incapacity_doc.append(child_field, {table_info["child_table_field"]: linked_doc["name"]})
                updated = True

    if updated:
        incapacity_doc.save(ignore_permissions=True)

    return {"message": "Linked documents updated"}

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

    trade_unions = frappe.get_all('Trade Union', fields=['name'])

    for tu in trade_unions:
        ss_list = frappe.get_all('Union Shop Stewards', filters={'parent': tu.name, 'parentfield': 'ss_list', 'ss_id': accused}, fields=['ss_id'])
        if ss_list:
            return {
                'is_ss': True,
                'ss_union': tu.name
            }
    return {
        'is_ss': False,
        'ss_union': None
    }
