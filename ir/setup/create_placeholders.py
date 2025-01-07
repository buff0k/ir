# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    # Define the documents to be created
    documents = [
        {
            "sec_head": "Working Hours Placeholder",
            "notes": "Placeholder",
            "sec_par": [{"doctype": "Contract Paragraph", "ss_num": "1", "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."}]
        },
        {
            "sec_head": "Remuneration Placeholder",
            "notes": "Placeholder",
            "sec_par": [{"doctype": "Contract Paragraph", "ss_num": "1", "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."}]
        }
    ]

    for doc in documents:
        # Manually create the document with the desired name, bypassing naming rules
        new_doc = frappe.new_doc("Contract Section")
        new_doc.name = doc["sec_head"]  # Explicitly set the name
        new_doc.sec_head = doc["sec_head"]
        new_doc.notes = doc["notes"]
        new_doc.sec_par = doc["sec_par"]

        # Insert the document without applying naming rules
        new_doc.flags.ignore_naming_rule = True
        new_doc.insert(ignore_permissions=True)

        # Automatically submit the document
        new_doc.submit()

    # Commit the transaction after all documents are created and submitted
    frappe.db.commit()

    # Log successful setup
    frappe.logger().info("Default Contract Section documents created and submitted successfully.")
