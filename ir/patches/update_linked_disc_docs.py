# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    frappe.flags.ignore_permissions = True

    # Step 1: Clear old linked fields from the Disciplinary Action Doctype
    frappe.db.sql("""
        UPDATE `tabDisciplinary Action`
        SET linked_nta = NULL, 
            linked_outcome = NULL, 
            linked_warning = NULL, 
            linked_dismissal = NULL, 
            linked_demotion = NULL, 
            linked_pay_deduction = NULL, 
            linked_pay_reduction = NULL, 
            linked_not_guilty = NULL, 
            linked_suspension = NULL, 
            linked_vsp = NULL, 
            linked_cancellation = NULL
    """)

    # Step 2: Map Table Multiselect fields to their respective linked Doctypes and fields in child tables
    linked_tables = {
        "linked_nta": {"doctype": "NTA Hearing", "child_table_field": "linked_nta"},
        "linked_outcome": {"doctype": "Disciplinary Outcome Report", "child_table_field": "linked_outcome"},
        "linked_warning": {"doctype": "Warning Form", "child_table_field": "linked_warning"},
        "linked_dismissal": {"doctype": "Dismissal Form", "child_table_field": "linked_dismissal"},
        "linked_demotion": {"doctype": "Demotion Form", "child_table_field": "linked_demotion"},
        "linked_pay_deduction": {"doctype": "Pay Deduction Form", "child_table_field": "linked_pay_deduction"},
        "linked_pay_reduction": {"doctype": "Pay Reduction Form", "child_table_field": "linked_pay_reduction"},
        "linked_not_guilty": {"doctype": "Not Guilty Form", "child_table_field": "linked_not_guilty"},
        "linked_suspension": {"doctype": "Suspension Form", "child_table_field": "linked_suspension"},
        "linked_vsp": {"doctype": "Voluntary Seperation Agreement", "child_table_field": "linked_vsp"},
        "linked_cancellation": {"doctype": "Hearing Cancellation Form", "child_table_field": "linked_cancellation"}
    }

    # Step 3: Get all Disciplinary Action documents
    disciplinary_actions = frappe.get_all("Disciplinary Action", fields=["name"])

    for disciplinary_action in disciplinary_actions:
        doc_name = disciplinary_action.name
        disciplinary_doc = frappe.get_doc("Disciplinary Action", doc_name)

        # Allow updates to submitted documents without validation errors
        disciplinary_doc.flags.ignore_validate_update_after_submit = True

        # Step 4: Clear existing data in the child tables
        for child_field in linked_tables.keys():
            disciplinary_doc.set(child_field, [])

        # Step 5: Populate the Table Multiselect fields
        for child_field, table_info in linked_tables.items():
            doctype_name = table_info["doctype"]
            child_table_field = table_info["child_table_field"]

            # Fetch linked documents for the current Doctype
            linked_docs = frappe.get_all(
                doctype_name, 
                filters={"linked_disciplinary_action": doc_name}, 
                fields=["name"]
            )

            # Append entries to the child table
            for linked_doc in linked_docs:
                disciplinary_doc.append(child_field, {
                    child_table_field: linked_doc["name"]  # Populate the correct field in the child table
                })

        # Save the updated Disciplinary Action document
        disciplinary_doc.save()

    # Commit changes to the database
    frappe.db.commit()
