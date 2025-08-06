# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.model.document import Document
from frappe.utils import getdate, formatdate

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
def fetch_incpacity_proceeding_data(incapacity_proceeding):
    data = frappe.db.get_value('Incapacity Proceedings', incapacity_proceeding, 
        ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company', 'complainant', 'compl_name', 'type_of_incapacity', 'details_of_incapacity'], as_dict=True)

    if not data:
        return {}
    
    # Fetch child table data
    incapacity_proceeding_doc = frappe.get_doc('Incapacity Proceedings', incapacity_proceeding)

    linked_nta_entries = [
        {"linked_nta": row.linked_nta} for row in incapacity_proceeding_doc.linked_nta
    ]
    
    previous_incapacity_outcomes = [
        {
            'incap_proc': row.incap_proc,
            'date': row.date,
            'sanction': row.sanction,
            'incap_details': row.incap_details
        } for row in incapacity_proceeding_doc.previous_incapacity_outcomes
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

def normalize_headings(content):
    """
    Normalize all Markdown headings (#, ##, ###) to ### (H3).
    """
    if not content:
        return content
    
    # Use regex to replace any number of # at the start of a line, with or without space, with ###
    normalized_content = re.sub(r'^#+\s?', '### ', content, flags=re.MULTILINE)
    return normalized_content

@frappe.whitelist()
def normalize_headings(content):
    """
    Normalize all Markdown headings (#, ##, ###) to ### (H3).
    Ensures correct formatting even if there is no space between # and text.
    """
    if not content:
        return content
    
    # Ensure that any heading (#, ##, ###, etc.) is converted to '### '
    normalized_content = re.sub(r'^(#{1,})\s*(\S.*)', r'### \2', content, flags=re.MULTILINE)
    return normalized_content

@frappe.whitelist()
def compile_outcome(docname):
    """
    Compile the outcome report for the given Disciplinary Outcome Report document.
    Formats headings, aligns details in a Markdown table, and compiles structured content.
    """
    # Fetch the document
    doc = frappe.get_doc("Disciplinary Outcome Report", docname)

    # Initialize the compiled outcome with a Markdown table header
    compiled_outcome = (
        "| **Field**                          | **Value**                           |\n"
        "|------------------------------------|-----------------------------------|\n"
    )

    # Determine the type of enquiry
    if doc.linked_disciplinary_action:
        enquiry_type = "Disciplinary"
    elif doc.linked_incapacity_proceeding:
        enquiry_type = "Incapacity"
    else:
        frappe.throw("No linked disciplinary action or incapacity proceeding found.")

    # Add employee details based on enquiry type
    if enquiry_type == "Disciplinary":
        compiled_outcome += f"| **Name of Accused Employee**       | {doc.names} ({doc.coy}) |\n"
        compiled_outcome += f"| **Name of Complainant**            | {doc.complainant_name} |\n"
    else:
        compiled_outcome += f"| **Name of Employee**               | {doc.names} ({doc.coy}) |\n"
        compiled_outcome += f"| **Name of Employer Representative** | {doc.complainant_name} |\n"

    # Add chairperson and date of enquiry
    compiled_outcome += f"| **Chairperson Name**               | {doc.chairperson_name} |\n"
    compiled_outcome += f"| **Date of Enquiry**                | {formatdate(doc.date_of_enquiry, 'd MMMM YYYY')} |\n\n"

    # Add the standard introductory paragraph
    compiled_outcome += (
        "This is the outcome of an enquiry conducted by myself on the {} and serves merely "
        "as a summary of the most salient points considered in arriving at my conclusion and does "
        "not purport to be a comprehensive, blow-by-blow recounting of the enquiry. Any failure to "
        "specifically refer to any fact or point does not mean that it was not considered in arriving at my conclusion.\n\n"
    ).format(formatdate(doc.date_of_enquiry, 'd MMMM YYYY'))

    # Define the markdown fields and their corresponding headings
    markdown_fields = {
        "introduction": "Introduction",
        "complainant_case": "Complainant's Case" if enquiry_type == "Disciplinary" else "Employer's Case",
        "accused_case": "Accused Employee Case" if enquiry_type == "Disciplinary" else "Employee Case",
        "analysis_of_evidence": "Analysis of Evidence",
        "finding": "Finding by Chairperson",
        "mitigating_considerations": "Mitigating Considerations",
        "aggravating_conisderations": "Aggravating Considerations",
        "outcome": "Outcome"
    }

    # Add each markdown field to the compiled outcome
    for field, heading in markdown_fields.items():
        content = doc.get(field)
        if content:
            # Normalize headings in the content
            normalized_content = normalize_headings(content)
            compiled_outcome += f"### {heading}\n\n{normalized_content}\n\n"

    # Update the complete_outcome field
    doc.complete_outcome = compiled_outcome
    doc.save()

    frappe.msgprint("Outcome compiled successfully.")