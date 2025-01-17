# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import formatdate
from bs4 import BeautifulSoup
import re

class DisciplinaryOutcomeReport(Document):
    def autoname(self):
        linked_field = None
        linked_field_name = None

        # Check which linked field is populated
        if self.linked_disciplinary_action:
            linked_field = self.linked_disciplinary_action
            linked_field_name = 'linked_disciplinary_action'
        elif self.linked_incapacity_proceeding:
            linked_field = self.linked_incapacity_proceeding
            linked_field_name = 'linked_incapacity_proceeding'

        # If neither linked field is populated, return None (default naming)
        if not linked_field:
            return

        # Check if this is the first document for the linked field
        existing_docs = frappe.get_all(self.doctype, filters={linked_field_name: linked_field}, fields=["name"])

        # If no existing documents are found, this is the first document
        if len(existing_docs) == 0:
            # Naming format for the first document
            self.name = f"OUT-{linked_field}"
        else:
            # If not the first document, find the latest revision number specific to this linked field
            latest_revision = 0
            for doc in existing_docs:
                # Extract the revision number (after the dash)
                if doc.name.startswith(f"OUT-{linked_field}-"):
                    revision_number = doc.name.split('-')[-1]
                    try:
                        revision_number = int(revision_number)
                        latest_revision = max(latest_revision, revision_number)
                    except ValueError:
                        pass  # Skip invalid revision numbers

            # Increment the revision number for the next document
            new_revision = latest_revision + 1
            self.name = f"OUT-{linked_field}-{new_revision}"

@frappe.whitelist()
def write_disciplinary_outcome_report(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_disciplinary_action = source_name

    doclist = get_mapped_doc("Disciplinary Action", source_name, {
        "Disciplinary Action": {
            "doctype": "Disciplinary Outcome Report",
            "field_map": {
                "name": "linked_disciplinary_action"
            }
        }
    }, target_doc, set_missing_values)

    return doclist

@frappe.whitelist()
def write_incapacity_outcome_report(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_incapacity_proceeding = source_name

    doclist = get_mapped_doc("Incapacity Proceedings", source_name, {
        "Incapacity Proceedings": {
            "doctype": "Disciplinary Outcome Report",
            "field_map": {
                "name": "linked_incapacity_proceeding"
            }
        }
    }, target_doc, set_missing_values)

    return doclist

@frappe.whitelist()
def fetch_disciplinary_action_data(disciplinary_action):
    data = frappe.db.get_value('Disciplinary Action', disciplinary_action, 
        ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company', 'complainant', 'compl_name'], as_dict=True)

    if not data:
        return {}

    # Fetch child table data
    disciplinary_action_doc = frappe.get_doc('Disciplinary Action', disciplinary_action)

    linked_nta_entries = [
        {"linked_nta": row.linked_nta} for row in disciplinary_action_doc.linked_nta
    ]
    
    previous_disciplinary_outcomes = [
        {
            'disc_action': row.disc_action,
            'date': row.date,
            'sanction': row.sanction,
            'charges': row.charges
        } for row in disciplinary_action_doc.previous_disciplinary_outcomes
    ]
    
    final_charges = [
        {
            'indiv_charge': f"({row.code_item}) {row.charge}"
        } for row in disciplinary_action_doc.final_charges
    ]
    
    data.update({
        'linked_nta': linked_nta_entries,
        'previous_disciplinary_outcomes': previous_disciplinary_outcomes,
        'final_charges': final_charges
    })
    
    return data

@frappe.whitelist()
def fetch_incpacity_proceeding_data(incapacity_proceedings):
    data = frappe.db.get_value('Incapacity Proceedings', incapacity_proceedings, 
        ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company', 'complainant', 'compl_name', 'type_of_incapacity', 'details_of_incapacity'], as_dict=True)

    if not data:
        return {}
    
    # Fetch child table data
    incapacity_proceedings_doc = frappe.get_doc('Incapacity Proceedings', incapacity_proceedings)

    linked_nta_entries = [
        {"linked_nta": row.linked_nta} for row in incapacity_proceedings_doc.linked_nta
    ]
    
    previous_incapacity_outcomes = [
        {
            'incap_proc': row.incap_proc,
            'date': row.date,
            'sanction': row.sanction,
            'incap_details': row.incap_details
        } for row in incapacity_proceedings_doc.previous_incapacity_outcomes
    ]
    
    data.update({
        'linked_nta': linked_nta_entries,
        'previous_incapacity_outcomes': previous_incapacity_outcomes
    })
    
    return data

@frappe.whitelist()
def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value('Company', company, 'default_letter_head')
    return {'letter_head': letter_head} if letter_head else {}

@frappe.whitelist()
def fetch_linked_fields(linked_nta=None, linked_disciplinary_action=None, linked_incapacity_proceeding=None):
    latest_nta = None
    chairperson = None
    complainant = None

    # Process linked_nta to find the latest NTA Hearing
    if linked_nta:
        if isinstance(linked_nta, str):  # Convert string to list if necessary
            linked_nta = frappe.parse_json(linked_nta)
        
        nta_names = [row.get('linked_nta') for row in linked_nta if row.get('linked_nta')]
        if nta_names:
            latest_nta = frappe.db.get_value(
                'NTA Hearing', 
                filters={"name": ("in", nta_names)}, 
                fieldname=["name"], 
                order_by="creation DESC"
            )

    # Fetch chairperson and complainant from the latest NTA Hearing
    if latest_nta:
        chairperson = frappe.db.get_value('NTA Hearing', latest_nta, 'chairperson')
        complainant = frappe.db.get_value('NTA Hearing', latest_nta, 'complainant')

    # If no linked_nta, fallback to other logic
    if linked_disciplinary_action and not complainant:
        complainant = frappe.db.get_value('Disciplinary Action', linked_disciplinary_action, 'complainant')

    if linked_incapacity_proceeding and not complainant:
        complainant = frappe.db.get_value('Incapacity Proceedings', linked_incapacity_proceeding, 'complainant')

    return {
        'chairperson': chairperson,
        'complainant': complainant,
    }

@frappe.whitelist()
def fetch_employee_names(chairperson=None, complainant=None):
    chairperson_name = None
    complainant_name = None

    if chairperson:
        chairperson_name = frappe.db.get_value('Employee', chairperson, 'employee_name')

    if complainant:
        complainant_name = frappe.db.get_value('Employee', complainant, 'employee_name')

    return {
        'chairperson_name': chairperson_name,
        'complainant_name': complainant_name,
    }

@frappe.whitelist()
def generate_numbered_html(content, paragraph_counter):
    """Generates numbered HTML content based on Quill's Delta format."""
    numbered_content = ""
    
    for item in content:
        if item.get("insert"):
            text = item["insert"].strip()
            if not text:  # Skip empty lines
                continue
            
            # Handle headings
            if "attributes" in item and "header" in item["attributes"]:
                header_level = item["attributes"]["header"]
                numbered_content += f"<h{header_level}>{text}</h{header_level}>"
            else:
                # Number paragraphs
                paragraph_counter += 1
                numbered_content += f"<p>{paragraph_counter}. {text}</p>"
    
    return numbered_content, paragraph_counter

@frappe.whitelist()
def compile_outcome(docname):
    doc = frappe.get_doc("Disciplinary Outcome Report", docname)

    # Fetch the linked NTA document's venue
    venue = ""
    if doc.linked_nta:
        linked_nta_doc = frappe.get_doc("NTA Hearing", doc.linked_nta)
        venue = linked_nta_doc.venue or "Unknown Venue"

    # Helper to convert a date to words
    def date_to_words(date_str):
        return frappe.utils.formatdate(date_str, "d MMMM yyyy")

    date_in_words = date_to_words(doc.date) if doc.date else "Unknown Date"

    # Start compiling the outcome
    outcome_content = f"""
        <h1 style="text-align:center;">OUTCOME OF A DISCIPLINARY ENQUIRY</h1>
        <h3>Held at {venue}, on the {date_in_words}, with:</h3>
        <p>Chairperson: {doc.chairperson_name or 'Unknown'}</p>
        <p>Complainant: {doc.complainant_name or 'Unknown'}</p>
        <p>Accused Employee: {doc.names or 'Unknown'} ({doc.coy or 'Unknown'})</p>
    """

    # Process sections with continuous numbering
    sections = [
        ("Introduction", doc.introduction),
        ("Complainant's Statement of Case", doc.complainant_case),
        ("Accused Employee's Statement of Case", doc.accused_case),
        ("Analysis of Evidence", doc.analysis_of_evidence),
        ("Finding", doc.finding),
        ("Mitigating Considerations", doc.mitigating_considerations),
        ("Aggravating Considerations", doc.aggravating_conisderations),  # Intentional typo
        ("Outcome", doc.outcome),
    ]

    paragraph_counter = 1  # Start numbering from 1
    for title, content in sections:
        if content:
            # Add section heading
            outcome_content += f"<h3>{title}</h3>"
            # Generate numbered content for the section
            numbered_html, paragraph_counter = generate_numbered_html(content, paragraph_counter)
            outcome_content += numbered_html

    # Save to the complete_outcome field
    doc.complete_outcome = outcome_content
    doc.save()

    return {"success": True}
