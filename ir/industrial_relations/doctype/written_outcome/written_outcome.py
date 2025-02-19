# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.model.document import Document
from frappe.utils import getdate, formatdate

class WrittenOutcome(Document):
    def autoname(self):
        if not self.ir_intervention or not self.linked_intervention:
            return
        
        linked_doc = self.linked_intervention
        existing_docs = frappe.get_all(self.doctype, filters={"linked_intervention": linked_doc}, fields=["name"])
        
        if len(existing_docs) == 0:
            self.name = f"OUT-{linked_doc}"
        else:
            latest_revision = max([int(doc.name.split("-")[-1]) for doc in existing_docs if "-" in doc.name] + [0])
            self.name = f"OUT-{linked_doc}-{latest_revision + 1}"

@frappe.whitelist()
def create_written_outcome(source_name, source_doctype, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.ir_intervention = source_doctype  # ✅ Store source document type
        target.linked_intervention = source_name  # ✅ Store source document reference

    field_maps = {
        "Disciplinary Action": {
            "accused": "employee",
            "accused_name": "employee_name",
            "accused_pos": "employee_designation",
            "company": "company",
            "linked_nta": "linked_nta",
            "previous_disciplinary_outcomes": "disciplinary_history",
            "final_charges": "nta_charges",
            "compl_name": "complainant_name",
            "branch": "employee_branch"
        },
        "Incapacity Proceedings": {
            "accused": "employee",
            "accused_name": "employee_name",
            "accused_pos": "employee_designation",
            "company": "company",
            "type_of_incapacity": "incap_type_nta",
            "details_of_incapacity": "incapacity_details_nta"
        },
        "Appeal": {
            "appellant": "employee",
            "appellant_name": "employee_name",
            "company": "company",
            "rulings": "linked_rulings"
        }
    }

    # ✅ Check if the source DocType exists in our mapping
    if source_doctype not in field_maps:
        frappe.throw(f"Unsupported source DocType: {source_doctype}")

    # ✅ Fetch the correct field mapping
    field_map = field_maps[source_doctype]

    # ✅ Perform the document mapping with field transformations
    doclist = get_mapped_doc(
        source_doctype, source_name, {
            source_doctype: {
                "doctype": "Written Outcome",
                "field_map": field_map
            }
        }, target_doc, set_missing_values
    )

    return doclist

@frappe.whitelist()
def fetch_intervention_data(intervention, intervention_type):
    # ✅ Define the field mappings for different intervention types
    field_maps = {
        "Disciplinary Action": {
            "source_fields": ["accused", "accused_name", "accused_pos", "company", "complainant", "branch", "compl_name"],
            "target_fields": ["employee", "employee_name", "employee_designation", "company", "complainant", "employee_branch", "complainant_name"]
        },
        "Incapacity Proceedings": {
            "source_fields": ["accused", "accused_name", "accused_pos", "company", "type_of_incapacity", "details_of_incapacity"],
            "target_fields": ["employee", "employee_name", "employee_designation", "company", "incap_type_nta", "incapacity_details_nta"]
        },
        "Appeal": {
            "source_fields": ["appellant", "appellant_name", "company"],
            "target_fields": ["employee", "employee_name", "company"]
        }
    }

    # ✅ Validate the intervention type
    if intervention_type not in field_maps:
        frappe.throw(f"Unsupported intervention type: {intervention_type}")

    # ✅ Get the correct field mapping
    mapping = field_maps[intervention_type]
    
    # ✅ Fetch data dynamically based on the mapping
    data = frappe.db.get_value(intervention_type, intervention, mapping["source_fields"], as_dict=True)
    
    if not data:
        return {}

    # ✅ Transform the data to match Written Outcome fields
    transformed_data = {target: data[source] for source, target in zip(mapping["source_fields"], mapping["target_fields"])}

    return transformed_data

@frappe.whitelist()
def normalize_headings(content):
    if not content:
        return content
    return re.sub(r'^(#{1,})\s*(\S.*)', r'### \2', content, flags=re.MULTILINE)

@frappe.whitelist()
def compile_outcome(docname):
    doc = frappe.get_doc("Written Outcome", docname)
    
    compiled_outcome = (
        "| **Field** | **Value** |\n"
        "|------------------------------------|-----------------------------------|\n"
        f"| **Employee Name** | {doc.employee_name} ({doc.employee_branch}) |\n"
        f"| **Chairperson** | {doc.chairperson_coy} |\n"
        f"| **Date of Enquiry** | {formatdate(doc.date_of_enquiry, 'd MMMM YYYY')} |\n\n"
    )
    
    markdown_fields = {
        "summary_introduction": "Introduction",
        "summary_complainant": "Complainant's Case",
        "summary_accused": "Accused Employee Case",
        "summary_analysis": "Analysis of Evidence",
        "summary_finding": "Finding by Chairperson",
        "summary_mitigation": "Mitigating Considerations",
        "summary_aggravation": "Aggravating Considerations",
        "summary_outcome": "Outcome"
    }
    
    for field, heading in markdown_fields.items():
        content = doc.get(field)
        if content:
            compiled_outcome += f"### {heading}\n\n{normalize_headings(content)}\n\n"
    
    doc.complete_outcome = compiled_outcome
    doc.save()
    frappe.msgprint("Outcome compiled successfully.")

@frappe.whitelist()
def get_linked_documents(disciplinary_action_name, linked_doctype, linking_field):
    """
    Fetch all documents of the specified doctype that are linked to the given Disciplinary Action.
    """
    frappe.flags.ignore_permissions = True  # Bypass permissions
    # Debugging: Print the input arguments
    frappe.logger().info(f"Fetching linked documents for {disciplinary_action_name} in {linked_doctype} with linking field {linking_field}")

    # Query to find all documents of the specified doctype that have the specified linking field equal to the given Disciplinary Action name.
    linked_docs = frappe.get_all(
        linked_doctype,
        filters={linking_field: disciplinary_action_name},
        fields=["name"]
    )

    # Debugging: Print the results of the query
    frappe.logger().info(f"Found {len(linked_docs)} linked documents: {linked_docs}")

    # Return the list of document names
    return [doc.name for doc in linked_docs]
