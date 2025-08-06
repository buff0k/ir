# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document
from frappe import _, get_doc

class HearingCancellationForm(Document):
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
            self.name = f"CAN-{linked_field}"
        else:
            # If not the first document, find the latest revision number specific to this linked field
            latest_revision = 0
            for doc in existing_docs:
                # Extract the revision number (after the dash)
                if doc.name.startswith(f"CAN-{linked_field}-"):
                    revision_number = doc.name.split('-')[-1]
                    try:
                        revision_number = int(revision_number)
                        latest_revision = max(latest_revision, revision_number)
                    except ValueError:
                        pass  # Skip invalid revision numbers

            # Increment the revision number for the next document
            new_revision = latest_revision + 1
            self.name = f"CAN-{linked_field}-{new_revision}"

    def before_save(self):
        if not getattr(self, "__confirmed_save", False):
            self.clear_outcome_in_linked_documents()

    def before_submit(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))

        employee = frappe.get_doc("Employee", self.employee)
        employee.status = "Active"
        employee.relieving_date = ""
        employee.save(ignore_permissions=True)

        frappe.msgprint(
            _("Employee {0}'s status has been updated to Active.").format(
                self.employee
            ),
            alert=True
        )

    def on_submit(self):
        if not getattr(self, "__confirmed_submit", False):
            self.set_outcome_in_linked_documents()

    def clear_outcome_in_linked_documents(self):
        linked_doc_name, linked_doctype = self.get_linked_document()
        if linked_doc_name and linked_doctype:
            linked_doc = frappe.get_doc(linked_doctype, linked_doc_name)
            linked_doc.flags.ignore_version = True  # Avoid version mismatch

            previous_outcome = linked_doc.get("outcome")
            previous_outcome_date = linked_doc.get("outcome_date")
            previous_outcome_start = linked_doc.get("outcome_start")
            previous_outcome_end = linked_doc.get("outcome_end")

            if linked_doc.docstatus == 0:  # Non-submitted document
                linked_doc.outcome = None
                linked_doc.outcome_date = None
                linked_doc.outcome_start = None
                linked_doc.outcome_end = None
                linked_doc.save(ignore_permissions=True)
            else:  # Submitted document
                linked_doc.db_set("outcome", None)
                linked_doc.db_set("outcome_date", None)
                linked_doc.db_set("outcome_start", None)
                linked_doc.db_set("outcome_end", None)
                # Create a manual version entry for the submitted document
                create_manual_version(linked_doc, "outcome", previous_outcome, None)
                create_manual_version(linked_doc, "outcome_date", previous_outcome_date, None)
                create_manual_version(linked_doc, "outcome_start", previous_outcome_date, None)
                create_manual_version(linked_doc, "outcome_end", previous_outcome_date, None)

            # Notify the user
            frappe.msgprint(
                _("Outcome, Outcome Date, Outcome Start, and Outcome End for {0} ({1}) have been cleared.").format(linked_doc_name, linked_doctype),
                alert=True
            )

    def set_outcome_in_linked_documents(self):
        linked_doc_name, linked_doctype = self.get_linked_document()
        if linked_doc_name and linked_doctype:
            linked_doc = frappe.get_doc(linked_doctype, linked_doc_name)
            linked_doc.flags.ignore_version = True  # Avoid version mismatch

            previous_outcome = linked_doc.get("outcome")
            previous_outcome_date = linked_doc.get("outcome_date")
            previous_outcome_start = linked_doc.get("outcome_start")
            previous_outcome_end = linked_doc.get("outcome_end")

            if linked_doc.docstatus == 0:  # Non-submitted document
                linked_doc.outcome = self.cancellation_type
                linked_doc.outcome_date = self.outcome_date
                linked_doc.save(ignore_permissions=True)
            else:  # Submitted document
                linked_doc.db_set("outcome", self.cancellation_type)
                linked_doc.db_set("outcome_date", self.outcome_date)

                # Create a manual version entry for the submitted document
                create_manual_version(linked_doc, "outcome", previous_outcome, self.cancellation_type)
                create_manual_version(linked_doc, "outcome_date", previous_outcome_date, self.outcome_date)

            # Notify the user
            frappe.msgprint(
                _("Outcome and Outcome Date for {0} ({1}) have been updated to {2} and {3}, respectively.")
                .format(linked_doc_name, linked_doctype, self.cancellation_type, self.outcome_date),
                alert=True
            )

    def get_linked_document(self):
        if self.linked_disciplinary_action:
            return self.linked_disciplinary_action, "Disciplinary Action"
        elif self.linked_incapacity_proceeding:
            return self.linked_incapacity_proceeding, "Incapacity Proceedings"
        return None, None

def create_manual_version(doc, fieldname, old_value, new_value):
    """Create a manual version entry for a submitted document."""
    version_data = {
        "ref_doctype": doc.doctype,
        "docname": doc.name,
        "data": frappe.as_json({
            "changed": [[fieldname, old_value, new_value]]
        })
    }
    frappe.get_doc({"doctype": "Version", **version_data}).insert(ignore_permissions=True)

@frappe.whitelist()
def cancel_disciplinary(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_disciplinary_action = source_name

    doclist = get_mapped_doc("Disciplinary Action", source_name, {
        "Disciplinary Action": {
            "doctype": "Hearing Cancellation Form",
            "field_map": {
                "name": "linked_disciplinary_action"
            }
        }
    }, target_doc, set_missing_values)

    return doclist

@frappe.whitelist()
def cancel_incapacity(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_incapacity_proceeding = source_name

    doclist = get_mapped_doc("Incapacity Proceedings", source_name, {
        "Incapacity Proceedings": {
            "doctype": "Hearing Cancellation Form",
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
def fetch_incapacity_proceeding_data(incapacity_proceeding):
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

@frappe.whitelist()
def fetch_authorizor_names(authorized_by=None):
    auth_names = None

    if authorized_by:
        auth_names = frappe.db.get_value('Employee', authorized_by, 'employee_name')

    return {
        'auth_names': auth_names,
    }

@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    linked_doc = frappe.get_doc(doctype, doc_name)
    return {
        "linked_doc_name": linked_doc.name,
        "linked_doctype": doctype,
        "outcome": linked_doc.outcome,
        "outcome_date": linked_doc.outcome_date,
        "outcome_start": linked_doc.outcome_start,
        "outcome_end": linked_doc.outcome_end
    }