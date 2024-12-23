# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document
from frappe import _


class DismissalForm(Document):
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
            self.name = f"DIS-{linked_field}"
        else:
            # If not the first document, find the latest revision number specific to this linked field
            latest_revision = 0
            for doc in existing_docs:
                # Extract the revision number (after the dash)
                if doc.name.startswith(f"DIS-{linked_field}-"):
                    revision_number = doc.name.split('-')[-1]
                    try:
                        revision_number = int(revision_number)
                        latest_revision = max(latest_revision, revision_number)
                    except ValueError:
                        pass  # Skip invalid revision numbers

            # Increment the revision number for the next document
            new_revision = latest_revision + 1
            self.name = f"DIS-{linked_field}-{new_revision}"

    def before_submit(self):
        # Ensure required fields are set
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))

        if not self.outcome_date:
            frappe.throw(_("Outcome Date is required before submitting."))

        # Fetch the Employee document
        employee = frappe.get_doc("Employee", self.employee)

        # Update Employee status and relieving date
        employee.status = "Left"
        employee.relieving_date = self.outcome_date

        # Save the Employee document to trigger Track Changes
        employee.save(ignore_permissions=True)

        frappe.msgprint(
            _("Employee {0}'s status has been updated to 'Left' and relieving date set to {1}.").format(
                self.employee, self.outcome_date
            ),
            alert=True
        )

@frappe.whitelist()
def make_dismissal_form(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_disciplinary_action = source_name

    doclist = get_mapped_doc("Disciplinary Action", source_name, {
        "Disciplinary Action": {
            "doctype": "Dismissal Form",
            "field_map": {
                "name": "linked_disciplinary_action"
            }
        }
    }, target_doc, set_missing_values)

    return doclist

@frappe.whitelist()
def make_dismissal_form_incap(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_incapacity_proceeding = source_name

    doclist = get_mapped_doc("Incapacity Proceedings", source_name, {
        "Incapacity Proceedings": {
            "doctype": "Dismissal Form",
            "field_map": {
                "name": "linked_incapacity_proceeding"
            }
        }
    }, target_doc, set_missing_values)

    return doclist

@frappe.whitelist()
def fetch_disciplinary_action_data(disciplinary_action):
    data = frappe.db.get_value('Disciplinary Action', disciplinary_action, 
        ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company'], as_dict=True)

    if not data:
        return {}
    
    # Fetch child table data
    disciplinary_action_doc = frappe.get_doc('Disciplinary Action', disciplinary_action)
    
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
        'previous_disciplinary_outcomes': previous_disciplinary_outcomes,
        'final_charges': final_charges
    })
    
    return data

@frappe.whitelist()
def fetch_incpacity_proceeding_data(incapacity_proceeding):
    # Check if the provided name exists and belongs to the correct DocType
    if not frappe.db.exists('Incapacity Proceedings', incapacity_proceeding):
        frappe.throw(_("Incapacity Proceedings {0} not found").format(incapacity_proceeding))

    data = frappe.db.get_value('Incapacity Proceedings', incapacity_proceeding, 
        ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company', 'type_of_incapacity', 'details_of_incapacity'], as_dict=True)

    if not data:
        return {}
    
    # Fetch child table data
    incapacity_proceeding_doc = frappe.get_doc('Incapacity Proceedings', incapacity_proceeding)
    
    previous_incapacity_outcomes = [
        {
            'incap_proc': row.incap_proc,
            'date': row.date,
            'sanction': row.sanction,
            'incap_details': row.incap_details
        } for row in incapacity_proceeding_doc.previous_incapacity_outcomes
    ]
    
    data.update({
        'previous_incapacity_outcomes': previous_incapacity_outcomes
    })
    
    return data

@frappe.whitelist()
def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value('Company', company, 'default_letter_head')
    return {'letter_head': letter_head} if letter_head else {}

