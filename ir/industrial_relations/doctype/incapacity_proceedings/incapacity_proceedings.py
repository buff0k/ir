# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months


class IncapacityProceedings(Document):
	pass

@frappe.whitelist()
def update_outcome_dates(doc_name):
    frappe.flags.ignore_permissions = True
    # Define the linked documents and relevant fields
    linked_docs = {
        'linked_demotion': 'Demotion Form',
        'linked_pay_reduction': 'Pay Reduction Form',
        'linked_suspension': 'Suspension Form'
    }

    relevant_fields = {
        'linked_demotion': ['from_date', 'to_date', 'Demoted from'],
        'linked_pay_reduction': ['from_date', 'to_date', 'Pay reduction effective from'],
        'linked_suspension': ['from_date', 'to_date', 'Suspended from']
    }
    
    doc = frappe.get_doc('Incapacity Proceedings', doc_name)
    latest_outcome_date = None
    latest_doc = None
    latest_outcome_type = None

    for link_field, doc_type in linked_docs.items():
        linked_doc_name = doc.get(link_field)
        if linked_doc_name:
            linked_doc = frappe.get_doc(doc_type, linked_doc_name)
            outcome_date = linked_doc.get('outcome_date')
            if outcome_date and (not latest_outcome_date or getdate(outcome_date) > getdate(latest_outcome_date)):
                latest_outcome_date = outcome_date
                latest_doc = linked_doc
                latest_outcome_type = link_field

    outcome_start = ""
    outcome_end = ""

    if latest_doc:
        if latest_outcome_type == 'linked_demotion':
            outcome_start = f"Demoted from {latest_doc.from_date}"
            outcome_end = f"until {latest_doc.to_date}" if latest_doc.to_date else ""
        elif latest_outcome_type == 'linked_pay_reduction':
            outcome_start = f"Pay reduction effective from {latest_doc.from_date}"
            outcome_end = f"until {latest_doc.to_date}" if latest_doc.to_date else ""
        elif latest_outcome_type == 'linked_suspension':
            outcome_start = f"Suspended from {latest_doc.from_date}"
            outcome_end = f"until {latest_doc.to_date}" if latest_doc.to_date else ""
    
    return {
        'outcome_start': outcome_start,
        'outcome_end': outcome_end
    }


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

    linked_docs = {
        "Dismissal Form": "linked_dismissal",
        "Demotion Form": "linked_demotion",
        "Pay Reduction Form": "linked_pay_reduction",
        "Not Guilty Form": "linked_not_guilty",
        "Suspension Form": "linked_suspension",
        "Voluntary Seperation Agreement": "linked_vsp",
        "Hearing Cancellation Form": "linked_cancellation"
    }

    relevant_fields = {
        "linked_dismissal": "dismissal_type",
        "linked_demotion": "demotion_type",
        "linked_pay_reduction": "pay_reduction_type",
        "linked_not_guilty": "type_of_not_guilty",
        "linked_suspension": "suspension_type",
        "linked_vsp": "vsp_type",
        "linked_cancellation": "cancellation_type"
    }

    result = {
        'linked_documents': {},
        'latest_outcome': None,
        'latest_outcome_date': None
    }

    for doctype, fieldname in linked_docs.items():
        docs = frappe.get_all(doctype, filters={'linked_incapacity_proceeding': doc_name}, fields=['name', 'outcome_date'])

        if docs:
            result['linked_documents'][fieldname] = [doc['name'] for doc in docs]
            for doc in docs:
                doc_outcome = frappe.db.get_value(doctype, doc['name'], relevant_fields[fieldname])
                if doc_outcome:
                    doc_outcome_date = doc['outcome_date']
                    if not result['latest_outcome_date'] or doc_outcome_date > result['latest_outcome_date']:
                        result['latest_outcome_date'] = doc_outcome_date
                        result['latest_outcome'] = doc_outcome
    
    return result

@frappe.whitelist()
def fetch_additional_linked_documents(doc_name):
    frappe.flags.ignore_permissions = True

    result = {
        'linked_nta': None,
        'linked_outcome': None
    }

    nta_hearing = frappe.get_all('NTA Hearing', filters={'linked_incapacity_proceeding': doc_name}, fields=['name'])
    disciplinary_outcome_report = frappe.get_all('Disciplinary Outcome Report', filters={'linked_incapacity_proceeding': doc_name}, fields=['name'])

    if nta_hearing:
        result['linked_nta'] = nta_hearing[0]['name']
    if disciplinary_outcome_report:
        result['linked_outcome'] = disciplinary_outcome_report[0]['name']
    
    return result

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

