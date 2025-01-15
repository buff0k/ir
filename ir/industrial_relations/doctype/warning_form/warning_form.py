# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document
from frappe import _, get_doc

class WarningForm(Document):
    def autoname(self):
        linked_field = None
        linked_field_name = None

        if self.linked_disciplinary_action:
            linked_field = self.linked_disciplinary_action
            linked_field_name = 'linked_disciplinary_action'

        if not linked_field:
            return

        existing_docs = frappe.get_all(self.doctype, filters={linked_field_name: linked_field}, fields=["name"])

        if len(existing_docs) == 0:
            self.name = f"WAR-{linked_field}"
        else:
            latest_revision = 0
            for doc in existing_docs:
                if doc.name.startswith(f"WAR-{linked_field}-"):
                    revision_number = doc.name.split('-')[-1]
                    try:
                        revision_number = int(revision_number)
                        latest_revision = max(latest_revision, revision_number)
                    except ValueError:
                        pass

            new_revision = latest_revision + 1
            self.name = f"WAR-{linked_field}-{new_revision}"

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
            _("Employee {0}'s status has been updated to 'Active'.").format(
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

            if linked_doc.docstatus == 0:  # Non-submitted document
                linked_doc.outcome = self.warning_type
                linked_doc.outcome_date = self.outcome_date
                linked_doc.save(ignore_permissions=True)
            else:  # Submitted document
                linked_doc.db_set("outcome", self.warning_type)
                linked_doc.db_set("outcome_date", self.outcome_date)
                # Create a manual version entry for the submitted document
                create_manual_version(linked_doc, "outcome", previous_outcome, self.warning_type)
                create_manual_version(linked_doc, "outcome_date", previous_outcome_date, self.outcome_date)

            # Notify the user
            frappe.msgprint(
                _("Outcome and Outcome Date for {0} ({1}) have been updated to {2} and {3}, respectively.")
                .format(linked_doc_name, linked_doctype, self.warning_type, self.outcome_date),
                alert=True
            )

    def get_linked_document(self):
        if self.linked_disciplinary_action:
            return self.linked_disciplinary_action, "Disciplinary Action"
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
def make_warning_form(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.linked_disciplinary_action = source_name

    doclist = get_mapped_doc("Disciplinary Action", source_name, {
        "Disciplinary Action": {
            "doctype": "Warning Form",
            "field_map": {
                "name": "linked_disciplinary_action"
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
def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value('Company', company, 'default_letter_head')
    return {'letter_head': letter_head} if letter_head else {}

@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    linked_doc = frappe.get_doc(doctype, doc_name)
    return {
        "linked_doc_name": linked_doc.name,
        "linked_doctype": doctype,
        "outcome": linked_doc.outcome,
        "outcome_date": linked_doc.outcome_date
    }