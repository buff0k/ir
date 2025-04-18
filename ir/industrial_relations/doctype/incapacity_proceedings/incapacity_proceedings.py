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
def get_linked_documents(incapacity_proceeding_name, linked_doctype, linking_field):
    """
    Fetch all documents of the specified doctype that are linked to the given Incapacity Proceeding.
    """
    frappe.flags.ignore_permissions = True  # Bypass permissions
    # Debugging: Print the input arguments
    frappe.logger().info(f"Fetching linked documents for {incapacity_proceeding_name} in {linked_doctype} with linking field {linking_field}")

    # Query to find all documents of the specified doctype that have the specified linking field equal to the given Incapacity Proceeding name.
    linked_docs = frappe.get_all(
        linked_doctype,
        filters={linking_field: incapacity_proceeding_name},
        fields=["name"]
    )

    # Debugging: Print the results of the query
    frappe.logger().info(f"Found {len(linked_docs)} linked documents: {linked_docs}")

    # Return the list of document names
    return [doc.name for doc in linked_docs]

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
